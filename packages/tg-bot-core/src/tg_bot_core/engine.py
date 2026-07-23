from __future__ import annotations

import logging
import json
from dataclasses import dataclass, replace
from typing import Any, Mapping

from .analytics import AnalyticsEventType, AnalyticsRecorder
from .catalog import CallbackCodec, ProjectCatalog
from .events import (
    Actor,
    CallbackEvent,
    CommandEvent,
    InteractionEvent,
    LifecycleEvent,
    MessageEvent,
)
from .handlers import HandlerExecutionError, HandlerExecutor
from .jobs import DurableJobQueue
from .outcomes import OutcomeRouter
from .project import ActionSpec, HandlerInvocation, ProjectDefinition
from .sdk import (
    ButtonContext,
    ChatInfo,
    CommandContext,
    LifecycleContext,
    MessageContext,
    StateValues,
    UserInfo,
)
from .store import FlowSession, SqliteStore
from .transport import BotTransport, OutboundButton, OutboundMessage

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _PendingAnalyticsEvent:
    event_type: AnalyticsEventType
    actor: Actor
    flow_id: str
    state_id: str | None = None


class FlowEngine:
    """Own flow/state lifecycle, actions, outcomes and session checkpoints."""

    def __init__(
        self,
        project: ProjectDefinition,
        catalog: ProjectCatalog,
        executor: HandlerExecutor,
        store: SqliteStore,
        queue: DurableJobQueue,
        transport: BotTransport,
        analytics: AnalyticsRecorder,
        *,
        max_auto_transitions: int,
    ) -> None:
        self.project = project
        self.catalog = catalog
        self.executor = executor
        self.store = store
        self.queue = queue
        self.transport = transport
        self.analytics = analytics
        self.codec = CallbackCodec()
        self.outcome_router = OutcomeRouter()
        self.max_auto_transitions = max_auto_transitions

    def active_message_handler(self, session: FlowSession) -> HandlerInvocation | None:
        if session.status != "active" or not session.flow_id or not session.state_id:
            return None
        flow = self.project.flows.get(session.flow_id)
        state = flow.states.get(session.state_id) if flow else None
        return state.on_message if state else None

    async def apply_action(
        self,
        session: FlowSession,
        action: ActionSpec,
        event: InteractionEvent,
        expected_kind: str,
    ) -> None:
        await self._apply_action(
            session, action, event, expected_kind, count=0, pending=[]
        )

    async def start_flow(self, session: FlowSession, flow_id: str, event: InteractionEvent) -> None:
        await self._start_flow(session, flow_id, event, count=0, pending=[])

    async def invoke_and_route(
        self,
        session: FlowSession,
        invocation: HandlerInvocation,
        event: InteractionEvent,
        expected_kind: str,
    ) -> None:
        await self._invoke_and_route(
            session, invocation, event, expected_kind, count=0, pending=[]
        )

    async def render_current(self, session: FlowSession) -> None:
        await self._save_and_render(session, self._current_view(session), [])

    def current_view(self, session: FlowSession) -> str:
        """Return the only view whose callback actions are active for a session."""

        return self._current_view(session)

    async def handle_error(self, session: FlowSession, event: InteractionEvent, error: Exception) -> None:
        # Rendering happens after the session checkpoint so transport/template
        # failures may occur with a newer persisted revision than the caller
        # holds. Reload before running the error boundary to avoid turning the
        # recovery itself into an optimistic-lock conflict.
        current = await self.store.load_session(session.bot_id, event.actor)
        await self._handle_error(current, event, error)

    async def _apply_action(
        self,
        session: FlowSession,
        action: ActionSpec,
        event: InteractionEvent,
        expected_kind: str,
        *,
        count: int,
        pending: list[_PendingAnalyticsEvent],
    ) -> None:
        count = self._next_count(count)
        if action.type == "noop":
            await self._save_and_render(session, self._current_view(session), pending)
            return
        if action.type == "view.render":
            if not action.target:
                raise RuntimeError("view.render requires a target.")
            await self._save_and_render(
                self._with_view(session, action.target), action.target, pending
            )
            return
        if action.type == "flow.start":
            if not action.target:
                raise RuntimeError("flow.start requires a target.")
            await self._start_flow(
                session, action.target, event, count=count, pending=pending
            )
            return
        if action.type == "flow.goto":
            if not action.target or not session.flow_id:
                raise RuntimeError("flow.goto requires an active flow and target state.")
            await self._enter_state(
                session,
                session.flow_id,
                action.target,
                event,
                count=count,
                pending=pending,
                exit_current=True,
            )
            return
        if action.type == "flow.cancel":
            await self._finish_flow(
                session,
                event,
                "cancelled",
                action.view,
                count=count,
                pending=pending,
            )
            return
        if action.type == "flow.finish":
            await self._finish_flow(
                session,
                event,
                "finished",
                action.view,
                count=count,
                pending=pending,
            )
            return
        if action.type == "flow.event":
            await self._emit_flow_event(
                session,
                action.target or "",
                event,
                count=count,
                pending=pending,
            )
            return
        if action.type == "handler.invoke":
            if not action.handler:
                raise RuntimeError("handler.invoke requires a handler.")
            await self._invoke_and_route(
                session,
                HandlerInvocation(action.handler, action.outcomes),
                event,
                expected_kind,
                payload=action.payload,
                count=count,
                pending=pending,
            )
            return
        if action.type == "task.enqueue":
            if not action.target:
                raise RuntimeError("task.enqueue requires a task handler target.")
            target_view = action.view or self._current_view(session)
            saved = await self.store.save_session(self._with_view(session, target_view))
            await self._flush_pending(pending)
            await self.queue.enqueue(action.target, action.payload, delay_seconds=action.delay_seconds)
            await self._render(saved, target_view)
            return
        raise RuntimeError(f"Unsupported action '{action.type}'.")

    async def _start_flow(
        self,
        previous: FlowSession,
        flow_id: str,
        event: InteractionEvent,
        *,
        count: int,
        pending: list[_PendingAnalyticsEvent],
    ) -> None:
        count = self._next_count(count)
        flow = self.project.flows[flow_id]
        if previous.status == "active" and previous.flow_id and previous.state_id:
            pending.append(
                _PendingAnalyticsEvent(
                    AnalyticsEventType.STATE_EXITED,
                    event.actor,
                    flow_id=previous.flow_id,
                    state_id=previous.state_id,
                )
            )
        pending.append(
            _PendingAnalyticsEvent(
                AnalyticsEventType.FLOW_STARTED,
                event.actor,
                flow_id=flow_id,
            )
        )
        session = replace(
            previous,
            flow_id=flow_id,
            state_id=flow.initial_state,
            view_id=None,
            variables={},
            status="active",
        )
        if flow.lifecycle.on_start:
            lifecycle_event = LifecycleEvent(event.actor, event.update_id, "on_start")
            session, route = await self._invoke(session, flow.lifecycle.on_start, lifecycle_event, "lifecycle")
            if route and route.type != "noop":
                await self._apply_action(
                    session,
                    route,
                    lifecycle_event,
                    "lifecycle",
                    count=count,
                    pending=pending,
                )
                return
        await self._enter_state(
            session,
            flow_id,
            flow.initial_state,
            event,
            count=count,
            pending=pending,
            exit_current=False,
        )

    async def _enter_state(
        self,
        session: FlowSession,
        flow_id: str,
        state_id: str,
        event: InteractionEvent,
        *,
        count: int,
        pending: list[_PendingAnalyticsEvent],
        exit_current: bool,
    ) -> None:
        count = self._next_count(count)
        flow = self.project.flows[flow_id]
        state = flow.states[state_id]
        if exit_current and session.flow_id and session.state_id:
            pending.append(
                _PendingAnalyticsEvent(
                    AnalyticsEventType.STATE_EXITED,
                    event.actor,
                    flow_id=session.flow_id,
                    state_id=session.state_id,
                )
            )
        pending.append(
            _PendingAnalyticsEvent(
                AnalyticsEventType.STATE_ENTERED,
                event.actor,
                flow_id=flow_id,
                state_id=state_id,
            )
        )
        variables = dict(session.variables or {})
        entered = replace(session, flow_id=flow_id, state_id=state_id, view_id=None, variables=variables, status="active")
        if state.on_enter:
            lifecycle_event = LifecycleEvent(event.actor, event.update_id, "on_enter")
            entered, route = await self._invoke(entered, state.on_enter, lifecycle_event, "lifecycle")
            if route and route.type != "noop":
                await self._apply_action(
                    entered,
                    route,
                    lifecycle_event,
                    "lifecycle",
                    count=count,
                    pending=pending,
                )
                return
        await self._save_and_render(
            self._with_view(entered, state.view), state.view, pending
        )

    async def _emit_flow_event(
        self,
        session: FlowSession,
        event_id: str,
        event: InteractionEvent,
        *,
        count: int,
        pending: list[_PendingAnalyticsEvent],
    ) -> None:
        if session.status != "active" or not session.flow_id or not session.state_id:
            await self._save_and_render(session, self._current_view(session), pending)
            return
        invocation = self.project.flows[session.flow_id].states[session.state_id].events.get(event_id)
        if invocation is None:
            log.warning("State %s.%s has no event '%s'", session.flow_id, session.state_id, event_id)
            await self._save_and_render(session, self._current_view(session), pending)
            return
        await self._invoke_and_route(
            session,
            invocation,
            event,
            "button",
            count=count,
            pending=pending,
        )

    async def _invoke_and_route(
        self,
        session: FlowSession,
        invocation: HandlerInvocation,
        event: InteractionEvent,
        expected_kind: str,
        *,
        payload: Mapping[str, Any] | None = None,
        count: int,
        pending: list[_PendingAnalyticsEvent],
    ) -> None:
        session, route = await self._invoke(session, invocation, event, expected_kind, payload)
        if route is None or route.type == "noop":
            await self._save_and_render(session, self._current_view(session), pending)
            return
        await self._apply_action(
            session,
            route,
            event,
            expected_kind,
            count=count,
            pending=pending,
        )

    async def _invoke(
        self,
        session: FlowSession,
        invocation: HandlerInvocation,
        event: InteractionEvent,
        expected_kind: str,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[FlowSession, ActionSpec | None]:
        state = StateValues(session.variables or {})
        actor = event.actor
        common = {
            "user": UserInfo(actor.user_id, actor.username, actor.first_name, actor.last_name, actor.role),
            "chat": ChatInfo(actor.chat_id),
            "event": event,
            "payload": dict(payload or {}),
            "state": state,
            "services": self.executor_services,
            "logger": logging.getLogger(f"handler.{invocation.handler}"),
        }
        if expected_kind == "button" and isinstance(event, CallbackEvent):
            context = ButtonContext(**common)
        elif expected_kind == "message" and isinstance(event, MessageEvent):
            context = MessageContext(**common)
        elif expected_kind == "command" and isinstance(event, CommandEvent):
            context = CommandContext(**common)
        elif expected_kind == "lifecycle" and isinstance(event, LifecycleEvent):
            context = LifecycleContext(**common)
        else:
            raise HandlerExecutionError(f"Cannot build {expected_kind} context for {type(event).__name__}.")
        result = await self.executor.execute(
            invocation.handler,
            expected_kind,
            context,
            metadata={
                "flow_id": session.flow_id,
                "state_id": session.state_id,
                "view_id": session.view_id,
            },
            actor=actor,
        )
        values = {**state.snapshot(), **dict(result.values)}
        try:
            json.dumps(values, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise HandlerExecutionError(
                f"Handler '{invocation.handler}' stored non-JSON session values."
            ) from error
        updated = replace(session, variables=values)
        return updated, self.outcome_router.route(invocation, result)

    @property
    def executor_services(self) -> Mapping[str, Any]:
        return self.executor.services

    async def _finish_flow(
        self,
        session: FlowSession,
        event: InteractionEvent,
        status: str,
        view: str | None,
        *,
        count: int,
        pending: list[_PendingAnalyticsEvent],
    ) -> None:
        flow = self.project.flows.get(session.flow_id or "")
        previous_flow_id = session.flow_id
        previous_state_id = session.state_id
        route: ActionSpec | None = None
        if flow:
            invocation = flow.lifecycle.on_complete if status == "finished" else flow.lifecycle.on_cancel
            if invocation:
                hook = "on_complete" if status == "finished" else "on_cancel"
                lifecycle_event = LifecycleEvent(event.actor, event.update_id, hook)
                session, route = await self._invoke(session, invocation, lifecycle_event, "lifecycle")
                event = lifecycle_event
        if previous_flow_id and previous_state_id:
            pending.append(
                _PendingAnalyticsEvent(
                    AnalyticsEventType.STATE_EXITED,
                    event.actor,
                    flow_id=previous_flow_id,
                    state_id=previous_state_id,
                )
            )
        if previous_flow_id:
            pending.append(
                _PendingAnalyticsEvent(
                    AnalyticsEventType.FLOW_COMPLETED
                    if status == "finished"
                    else AnalyticsEventType.FLOW_CANCELLED,
                    event.actor,
                    flow_id=previous_flow_id,
                )
            )
        finished = replace(session, flow_id=None, state_id=None, status=status)
        if route and route.type != "noop":
            await self._apply_action(
                finished,
                route,
                event,
                "lifecycle",
                count=count,
                pending=pending,
            )
            return
        target = view or self.project.manifest.entry_view
        await self._save_and_render(
            self._with_view(finished, target), target, pending
        )

    async def _handle_error(self, session: FlowSession, event: InteractionEvent, error: Exception) -> None:
        log.exception("Custom handler dispatch failed", exc_info=error)
        flow = self.project.flows.get(session.flow_id or "")
        pending: list[_PendingAnalyticsEvent] = []
        if flow and session.flow_id:
            if session.state_id:
                pending.append(
                    _PendingAnalyticsEvent(
                        AnalyticsEventType.STATE_EXITED,
                        event.actor,
                        flow_id=session.flow_id,
                        state_id=session.state_id,
                    )
                )
            pending.append(
                _PendingAnalyticsEvent(
                    AnalyticsEventType.FLOW_FAILED,
                    event.actor,
                    flow_id=session.flow_id,
                )
            )
        if flow and flow.lifecycle.on_error:
            try:
                lifecycle_event = LifecycleEvent(event.actor, event.update_id, "on_error")
                failed, route = await self._invoke(session, flow.lifecycle.on_error, lifecycle_event, "lifecycle", {"error": str(error)})
                failed = replace(failed, flow_id=None, state_id=None, status="failed")
                if route and route.type != "noop":
                    await self._apply_action(
                        failed,
                        route,
                        lifecycle_event,
                        "lifecycle",
                        count=0,
                        pending=pending,
                    )
                    return
                await self._save_and_render(
                    self._with_view(failed, self.project.manifest.entry_view),
                    self.project.manifest.entry_view,
                    pending,
                )
                return
            except Exception:
                log.exception("Flow on_error handler failed")
        current = await self.store.load_session(session.bot_id, event.actor)
        failed = replace(current, flow_id=None, state_id=None, status="failed")
        saved = await self.store.save_session(failed)
        await self._flush_pending(pending)
        try:
            await self.transport.send(
                OutboundMessage(saved.actor.chat_id, "The bot could not complete that action.")
            )
        except Exception:
            log.exception("Could not deliver the generic flow error message")

    async def _save_and_render(
        self,
        session: FlowSession,
        view_id: str,
        pending: list[_PendingAnalyticsEvent],
    ) -> FlowSession:
        saved = await self.store.save_session(self._with_view(session, view_id))
        await self._flush_pending(pending)
        await self._render(saved, view_id)
        return saved

    async def _render(self, session: FlowSession, view_id: str) -> None:
        actor = session.actor
        values = {
            **(session.variables or {}),
            "user": {
                "id": actor.user_id,
                "username": actor.username,
                "first_name": actor.first_name,
                "last_name": actor.last_name,
                "role": actor.role,
            },
        }
        text, keyboard = self.catalog.render(view_id, values)
        outbound = tuple(
            tuple(OutboundButton(button.text, self.codec.encode(button.id)) for button in row)
            for row in keyboard
        )
        await self.transport.send(OutboundMessage(actor.chat_id, text, outbound))
        await self.analytics.record(
            AnalyticsEventType.VIEW_RENDERED,
            actor=actor,
            flow_id=session.flow_id,
            state_id=session.state_id,
            view_id=view_id,
        )

    async def _flush_pending(
        self, pending: list[_PendingAnalyticsEvent]
    ) -> None:
        for item in pending:
            await self.analytics.record(
                item.event_type,
                actor=item.actor,
                flow_id=item.flow_id,
                state_id=item.state_id,
            )
        pending.clear()

    def _current_view(self, session: FlowSession) -> str:
        if session.view_id and session.view_id in self.project.views:
            return session.view_id
        if session.status == "active" and session.flow_id and session.state_id:
            flow = self.project.flows.get(session.flow_id)
            state = flow.states.get(session.state_id) if flow else None
            if state:
                return state.view
        return self.project.manifest.entry_view

    @staticmethod
    def _with_view(session: FlowSession, view_id: str) -> FlowSession:
        return replace(session, view_id=view_id)

    def _next_count(self, count: int) -> int:
        count += 1
        if count > self.max_auto_transitions:
            raise HandlerExecutionError("Flow exceeded the automatic transition limit.")
        return count
