from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Sequence
from dataclasses import replace

from .catalog import ProjectCatalog
from .config import BotConfig
from .dispatcher import EventDispatcher
from .engine import FlowEngine
from .events import InteractionEvent
from .handlers import HandlerExecutor, HandlerResolver
from .jobs import DurableJobQueue, JobRuntime
from .project import ProjectDefinition, ProjectValidationError, load_and_validate_project
from .services import ServiceContainer, ServiceProvider
from .store import SessionConflict, SqliteStore
from .transport import BotTransport, UserProfileProvider

log = logging.getLogger(__name__)


class BotApp:
    """Composition root for an autonomous bot project."""

    def __init__(
        self,
        *,
        config: BotConfig,
        services: Sequence[ServiceProvider] = (),
        transport: BotTransport | None = None,
    ) -> None:
        self.config = config
        self.service_providers = tuple(services)
        self.transport = transport
        self.project: ProjectDefinition | None = None
        self.catalog: ProjectCatalog | None = None
        self.service_container = ServiceContainer()
        self.store = SqliteStore(config.database_path)
        self.queue = DurableJobQueue(self.store)
        self.handler_executor: HandlerExecutor | None = None
        self.engine: FlowEngine | None = None
        self.dispatcher: EventDispatcher | None = None
        self.jobs: JobRuntime | None = None
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._transport_started = False
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        log.info("Starting bot runtime from %s", self.config.project_root)
        self._stop.clear()
        try:
            project, diagnostics = load_and_validate_project(
                self.config.project_root,
                inspect_code=True,
            )
            errors = [item for item in diagnostics if item.level == "error"]
            if errors:
                raise ProjectValidationError(errors)
            if project is None:  # Kept explicit for type narrowing and future report levels.
                raise ProjectValidationError(diagnostics)
            await self.store.initialize()
            await self.service_container.build(self.service_providers)
            resolver = HandlerResolver(project.handlers, project.root, project.manifest.package)
            resolver.validate_all()
            executor = HandlerExecutor(resolver, self.service_container.all())
            catalog = ProjectCatalog(project)
            await self.queue.sync_schedules(project.schedules)
            jobs = JobRuntime(self.queue, executor, self.service_container.all())
            if self.transport is None:
                if not self.config.token:
                    raise RuntimeError("BOT_TOKEN is required when no custom transport is provided.")
                from .adapters.ptb import PtbTransport

                self.transport = PtbTransport(self.config.token)
            engine = FlowEngine(
                project,
                catalog,
                executor,
                self.store,
                self.queue,
                self.transport,
                max_auto_transitions=self.config.max_auto_transitions,
            )
            self.project = project
            self.catalog = catalog
            self.handler_executor = executor
            self.jobs = jobs
            self.engine = engine
            self.dispatcher = EventDispatcher(project, catalog, engine)
            await self.transport.start(self.handle_event)
            self._transport_started = True
            self._tasks = [asyncio.create_task(self._supervise("scheduler", jobs.scheduler_loop))]
            self._tasks.extend(
                asyncio.create_task(self._supervise(f"worker-{index}", jobs.worker_loop))
                for index in range(self.config.worker_count)
            )
            self._started = True
            log.info(
                "Bot runtime started: bot_id=%s workers=%d schedules=%d",
                project.manifest.id,
                self.config.worker_count,
                len(project.schedules),
            )
        except Exception:
            log.exception("Bot runtime failed during startup.")
            await self.stop()
            raise

    async def stop(self) -> None:
        log.info("Stopping bot runtime.")
        self._stop.set()
        if self.jobs:
            self.jobs.stop()
        if self._tasks:
            done, pending = await asyncio.wait(self._tasks, timeout=10)
            if pending:
                log.warning("Timed out waiting for %d background task(s); cancelling them.", len(pending))
                for task in pending:
                    task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)
        self._tasks.clear()
        if self.transport and (self._transport_started or not self._started):
            try:
                await self.transport.stop()
            except Exception:
                log.exception("Transport shutdown failed.")
        self._transport_started = False
        try:
            await self.service_container.close()
        except Exception:
            log.exception("Service shutdown failed.")
        self._started = False
        log.info("Bot runtime stopped.")

    async def handle_event(self, event: InteractionEvent) -> None:
        if self.project is None or self.dispatcher is None:
            raise RuntimeError("BotApp is not started.")
        bot_id = self.project.manifest.id
        managed_user = await self.store.upsert_user(bot_id, event.actor)
        if managed_user.blocked:
            log.info("Ignoring update from blocked user: bot_id=%s user_id=%s", bot_id, event.actor.user_id)
            return
        if isinstance(self.transport, UserProfileProvider):
            try:
                avatar = await self.transport.fetch_user_avatar(
                    event.actor.user_id, managed_user.avatar_file_id
                )
                if avatar.file_id != managed_user.avatar_file_id:
                    await self.store.update_user_avatar(
                        bot_id,
                        event.actor.user_id,
                        file_id=avatar.file_id,
                        data=avatar.data,
                        mime_type=avatar.mime_type,
                    )
            except Exception:
                # User management must not make normal bot interactions depend on
                # Telegram's profile-photo endpoint being available.
                log.warning(
                    "Could not refresh Telegram profile photo: bot_id=%s user_id=%s",
                    bot_id,
                    event.actor.user_id,
                    exc_info=True,
                )
        if event.actor.role != managed_user.role:
            event = replace(event, actor=replace(event.actor, role=managed_user.role))
        if not await self.store.mark_update_once(bot_id, event.actor, event.update_id):
            return
        for _ in range(2):
            session = await self.store.load_session(bot_id, event.actor)
            try:
                await self.dispatcher.dispatch(session, event)
                return
            except SessionConflict:
                continue
        raise SessionConflict("Could not apply update after retrying optimistic session conflicts.")

    async def run_async(self) -> None:
        loop = asyncio.get_running_loop()
        loop_handlers: list[signal.Signals] = []
        fallback_handlers: dict[signal.Signals, object] = {}
        started = False

        def request_stop(*_args: object) -> None:
            loop.call_soon_threadsafe(self._stop.set)

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(signum, request_stop)
                loop_handlers.append(signum)
                continue
            except (NotImplementedError, RuntimeError):
                pass
            try:
                fallback_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, request_stop)
            except (OSError, RuntimeError, ValueError):
                # Signal registration is unavailable outside the main thread on
                # some event loops. Embedders can still call ``stop()``.
                fallback_handlers.pop(signum, None)
        try:
            await self.start()
            started = True
            await self._stop.wait()
        finally:
            # ``start`` already performs its own cleanup on failure. Avoid a
            # second shutdown pass (and duplicate lifecycle log messages).
            if started:
                await self.stop()
            for signum in loop_handlers:
                loop.remove_signal_handler(signum)
            for signum, previous in fallback_handlers.items():
                try:
                    signal.signal(signum, previous)  # type: ignore[arg-type]
                except (OSError, RuntimeError, ValueError):
                    pass

    def run(self) -> None:
        asyncio.run(self.run_async())

    async def _supervise(self, name: str, run) -> None:
        delay = 0.25
        while not self._stop.is_set():
            try:
                await run()
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Supervised service %s failed; restarting", name)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 10)
