from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from typing import Any, Mapping

from .config import BotConfig, StartPolicy
from .events import Actor, CallbackEvent, CommandEvent, EnterEvent, InteractionEvent
from .flows import FlowDefinition, FlowState, Transition, TransitionKind
from .jobs import DurableJobQueue, JobRuntime
from .module import BotModule, Container
from .resources import CallbackCodec, ViewCatalog
from .store import FlowSession, SessionConflict, SqliteStore
from .transport import BotTransport, OutboundButton, OutboundMessage

log = logging.getLogger(__name__)


@dataclass(slots=True)
class FlowContext:
    app: "BotApp"
    session: FlowSession
    event: InteractionEvent
    values: dict[str, Any]

    @property
    def services(self) -> Mapping[str, Any]:
        return self.app.services.all()

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value


class BotApp:
    """Explicit v2 application runtime with no plugins or hidden discovery."""

    def __init__(self, *, config: BotConfig, module: BotModule, transport: BotTransport | None = None) -> None:
        self.config = config
        self.module = module
        self.services = Container()
        self.store = SqliteStore(config.database_path)
        self.catalog = ViewCatalog(config.resource_root)
        self.codec = CallbackCodec()
        self.flows: dict[str, FlowDefinition] = {}
        self.queue = DurableJobQueue(self.store)
        self.jobs: JobRuntime | None = None
        self.transport = transport
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        try:
            await self.store.initialize()
            await self.catalog.load()
            self.flows = self.module.flow_map()
            if self.catalog.manifest.start_flow not in self.flows:
                raise RuntimeError(f"Manifest start_flow '{self.catalog.manifest.start_flow}' is not registered.")
            await self.services.build(self.module.services)
            await self.queue.sync_schedules(tuple(self.module.schedules))
            self.jobs = JobRuntime(self.queue, self.module.task_map(), self.services.all())
            if self.transport is None:
                if not self.config.token:
                    raise RuntimeError("BOT_TOKEN is required when no custom transport is provided.")
                from .adapters.ptb import PtbTransport
                self.transport = PtbTransport(self.config.token, self.codec)
            await self.transport.start(self.handle_event)
            self._tasks = [asyncio.create_task(self._supervise("scheduler", self.jobs.scheduler_loop))]
            self._tasks.extend(asyncio.create_task(self._supervise(f"worker-{index}", self.jobs.worker_loop)) for index in range(self.config.worker_count))
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        self._stop.set()
        if self.jobs:
            self.jobs.stop()
        if self._tasks:
            done, pending = await asyncio.wait(self._tasks, timeout=10)
            if pending:
                log.warning("Timed out waiting for %d background service(s); cancelling them.", len(pending))
                for task in pending:
                    task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)
        self._tasks = []
        if self.transport:
            try:
                await self.transport.stop()
            except Exception:
                log.exception("Transport shutdown failed.")

    async def run_async(self) -> None:
        try:
            await self.start()
            await self._stop.wait()
        finally:
            await self.stop()

    def run(self) -> None:
        asyncio.run(self.run_async())

    async def handle_event(self, event: InteractionEvent) -> None:
        if not await self.store.mark_update_once(self.config.bot_id, event.actor, event.update_id):
            return
        for _ in range(2):
            session = await self.store.load_session(self.config.bot_id, event.actor)
            try:
                await self._dispatch(session, event)
                return
            except SessionConflict:
                continue
        raise SessionConflict("Could not apply update after retrying optimistic session conflicts.")

    async def _dispatch(self, session: FlowSession, event: InteractionEvent) -> None:
        if isinstance(event, CommandEvent) and event.command == "start":
            if self.config.start_policy == StartPolicy.RESUME and session.status == "active":
                await self._render(session, self._current_view(session))
                return
            await self._start_flow(event, self.catalog.manifest.start_flow)
            return
        if isinstance(event, CallbackEvent):
            action_type = event.action.get("type")
            target = event.action.get("target")
            if action_type == "navigate" and target:
                session = replace(session, variables={**(session.variables or {}), "_view": target})
                saved = await self.store.save_session(session)
                await self._render(saved, target)
                return
            if action_type == "flow.start" and target:
                await self._start_flow(event, target)
                return
            if action_type == "flow.cancel":
                saved = await self.store.save_session(replace(session, flow_id=None, state_id=None, status="cancelled"))
                await self._render(saved, self.catalog.manifest.entry_view)
                return
        if session.status == "active" and session.flow_id and session.state_id:
            flow = self._flow(session.flow_id)
            handler = flow.state(session.state_id).handler_for(event)
            if handler is not None:
                context = FlowContext(self, session, event, dict(session.variables or {}))
                await self._apply_transition(flow, context, await handler(context, event))
                return
        await self._render(session, self._current_view(session))

    async def _start_flow(self, event: InteractionEvent, flow_id: str) -> None:
        flow = self._flow(flow_id)
        session = FlowSession(self.config.bot_id, event.actor, flow_id, flow.initial_state, {}, status="active")
        state = flow.state(flow.initial_state)
        if state.on_enter is None:
            saved = await self.store.save_session(session)
            await self._render(saved, self.catalog.manifest.entry_view)
            return
        enter = EnterEvent(actor=event.actor, update_id=event.update_id)
        context = FlowContext(self, session, enter, {})
        await self._apply_transition(flow, context, await state.on_enter(context, enter))

    async def _apply_transition(self, flow: FlowDefinition, context: FlowContext, transition: Transition) -> None:
        auto_count = 0
        current = transition
        session = context.session
        while True:
            auto_count += 1
            if auto_count > self.config.max_auto_transitions:
                current = Transition.fail("Flow exceeded the automatic transition limit.")
            values = {**(session.variables or {}), **context.values, **dict(current.variables)}
            if current.kind == TransitionKind.GOTO:
                if not current.state:
                    raise RuntimeError("Goto transition requires a target state.")
                next_state = flow.state(current.state)
                session = replace(session, state_id=current.state, variables=values, status="active")
                if current.view:
                    session = replace(session, variables={**values, "_view": current.view})
                if next_state.on_enter is None:
                    saved = await self.store.save_session(session)
                    if current.view:
                        await self._render(saved, current.view)
                    return
                context = FlowContext(self, session, EnterEvent(context.event.actor, context.event.update_id), dict(session.variables or {}))
                current = await next_state.on_enter(context, context.event)
                continue
            if current.kind == TransitionKind.RENDER:
                if not current.view:
                    raise RuntimeError("Render transition requires a view.")
                saved = await self.store.save_session(replace(session, variables={**values, "_view": current.view}, status="active"))
                await self._render(saved, current.view)
                return
            if current.kind == TransitionKind.SEND:
                saved = await self.store.save_session(replace(session, variables=values, status="active"))
                await self._send_text(saved.actor.chat_id, current.text or "")
                return
            if current.kind == TransitionKind.ENQUEUE:
                saved = await self.store.save_session(replace(session, variables=values, status="active"))
                if current.job is None:
                    raise RuntimeError("Enqueue transition requires a job.")
                await self.queue.enqueue(current.job.task, current.job.payload, delay_seconds=current.job.delay_seconds)
                if current.view:
                    await self._render(saved, current.view)
                return
            if current.kind in {TransitionKind.FINISH, TransitionKind.CANCEL, TransitionKind.FAIL}:
                status = "finished" if current.kind == TransitionKind.FINISH else "cancelled" if current.kind == TransitionKind.CANCEL else "failed"
                saved = await self.store.save_session(replace(session, flow_id=None, state_id=None, variables=values, status=status))
                if current.view:
                    await self._render(saved, current.view)
                elif current.kind == TransitionKind.FAIL:
                    await self._send_text(saved.actor.chat_id, current.error or "Flow failed.")
                return
            raise RuntimeError(f"Unsupported transition: {current.kind}")

    async def _render(self, session: FlowSession, view_id: str) -> None:
        if self.transport is None:
            raise RuntimeError("Transport is not initialized.")
        variables = {**(session.variables or {}), "user": {"id": session.actor.user_id, "username": session.actor.username, "first_name": session.actor.first_name, "last_name": session.actor.last_name}}
        text, keyboard = self.catalog.render(view_id, variables)
        outbound_keyboard = tuple(tuple(OutboundButton(button.text, self.codec.encode(button.action)) for button in row) for row in keyboard)
        await self.transport.send(OutboundMessage(session.actor.chat_id, text, outbound_keyboard))

    async def _send_text(self, chat_id: int, text: str) -> None:
        if self.transport is None:
            raise RuntimeError("Transport is not initialized.")
        await self.transport.send(OutboundMessage(chat_id, text))

    def _current_view(self, session: FlowSession) -> str:
        value = (session.variables or {}).get("_view")
        return value if isinstance(value, str) else self.catalog.manifest.entry_view

    def _flow(self, flow_id: str) -> FlowDefinition:
        try:
            return self.flows[flow_id]
        except KeyError as error:
            raise RuntimeError(f"Flow '{flow_id}' is not registered in BotModule.") from error

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
