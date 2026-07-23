from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Sequence
from dataclasses import replace

from .analytics import (
    AnalyticsEventType,
    AnalyticsRecorder,
    SqliteAnalyticsEventWriter,
)
from .catalog import ProjectCatalog
from .config import BotConfig
from .dispatcher import EventDispatcher
from .engine import FlowEngine
from .events import CallbackEvent, CommandEvent, InteractionEvent, MessageEvent
from .handlers import HandlerExecutor, HandlerResolver
from .jobs import DurableJobQueue, JobRuntime
from .project import ProjectDefinition, ProjectValidationError, load_and_validate_project
from .services import ServiceContainer, ServiceProvider
from .store import FlowSession, SessionConflict, SqliteStore
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
        self.analytics: AnalyticsRecorder | None = None
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
            analytics = AnalyticsRecorder(
                project.manifest.id,
                SqliteAnalyticsEventWriter(self.store.path),
            )
            await self.service_container.build(self.service_providers)
            resolver = HandlerResolver(project.handlers, project.root, project.manifest.package)
            resolver.validate_all()
            executor = HandlerExecutor(resolver, self.service_container.all(), analytics)
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
                analytics,
                max_auto_transitions=self.config.max_auto_transitions,
            )
            self.project = project
            self.catalog = catalog
            self.analytics = analytics
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
        managed_user, created = await self.store.upsert_user_with_status(bot_id, event.actor)
        if self.analytics is None:
            raise RuntimeError("BotApp analytics recorder is not initialized.")
        if created:
            await self.analytics.record(
                AnalyticsEventType.USER_FIRST_SEEN,
                actor=event.actor,
            )
        await self.analytics.record(
            AnalyticsEventType.INTERACTION_RECEIVED,
            actor=event.actor,
        )
        if managed_user.blocked:
            session = (
                await self.store.load_session(bot_id, event.actor)
                if isinstance(event, CallbackEvent)
                else None
            )
            await self._record_interaction_subtype(event, session)
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
        session = await self.store.load_session(bot_id, event.actor)
        await self._record_interaction_subtype(event, session)
        for attempt in range(2):
            if attempt:
                session = await self.store.load_session(bot_id, event.actor)
            try:
                await self.dispatcher.dispatch(session, event)
                return
            except SessionConflict:
                continue
        raise SessionConflict("Could not apply update after retrying optimistic session conflicts.")

    async def _record_interaction_subtype(
        self,
        event: InteractionEvent,
        session: FlowSession | None,
    ) -> None:
        if self.analytics is None:
            return
        if isinstance(event, CommandEvent):
            await self.analytics.record(
                AnalyticsEventType.COMMAND_RECEIVED,
                actor=event.actor,
                resource_id=event.command.lower().removeprefix("/"),
            )
            return
        if isinstance(event, MessageEvent):
            await self.analytics.record(
                AnalyticsEventType.MESSAGE_RECEIVED,
                actor=event.actor,
            )
            return
        if isinstance(event, CallbackEvent):
            await self.analytics.record(
                AnalyticsEventType.BUTTON_CLICKED,
                actor=event.actor,
                resource_id=event.action_id,
                flow_id=session.flow_id if session else None,
                state_id=session.state_id if session else None,
                view_id=session.view_id if session else None,
            )

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
