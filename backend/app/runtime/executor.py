from __future__ import annotations

import traceback
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from app.domain.enums import (
    ActionResultStatus,
    NodeType,
    SessionStatus,
    TransitionKind,
    VariableType,
)
from app.domain.flow import Flow, Node, Transition
from app.domain.ports.projects import ProjectRepository
from app.domain.ports.sessions import SessionRepository
from app.domain.project import BotProject, utc_now
from app.domain.session import InputExpectation, Session

from .actions import ActionInvoker
from .conditions import ConditionEvaluator
from .errors import (
    ActionExecutionError,
    BotRuntimeError,
    ExecutionGuardError,
    FlowNotFoundError,
    InvalidNodeConfigurationError,
    MissingTransitionError,
    NodeNotFoundError,
    RuntimeErrorContext,
)
from .events import RuntimeEventSink
from .input_validation import InputValidator
from .locks import SessionLockPool
from .templating import StrictTemplateRenderer
from .transitions import TransitionResolver
from .transport import (
    IncomingUpdate,
    Keyboard,
    KeyboardButton,
    KeyboardKind,
    MediaKind,
    OutboundMessage,
    TelegramPort,
    UpdateKind,
)


class GraphExecutor:
    """Execute one project's graph against durable sessions."""

    def __init__(
        self,
        *,
        project: BotProject,
        project_root: Path,
        projects: ProjectRepository,
        sessions: SessionRepository,
        telegram: TelegramPort,
        actions: ActionInvoker,
        events: RuntimeEventSink,
        max_automatic_steps: int = 64,
        locks: SessionLockPool | None = None,
        templates: StrictTemplateRenderer | None = None,
        transitions: TransitionResolver | None = None,
        conditions: ConditionEvaluator | None = None,
        inputs: InputValidator | None = None,
    ) -> None:
        self.project = project
        self.project_root = project_root.resolve()
        self._projects = projects
        self._sessions = sessions
        self._telegram = telegram
        self._actions = actions
        self._events = events
        self._guard_limit = max(1, int(max_automatic_steps))
        self._locks = locks or SessionLockPool()
        self._templates = templates or StrictTemplateRenderer()
        self._transitions = transitions or TransitionResolver()
        self._conditions = conditions or ConditionEvaluator()
        self._inputs = inputs or InputValidator()

    async def handle_update(self, update: IncomingUpdate) -> Session | None:
        key = (
            self.project.id,
            update.telegram_user_id,
            update.telegram_chat_id,
        )
        async with self._locks.acquire(key):
            try:
                return await self._handle_locked(update)
            except Exception as exc:
                session = self._sessions.find_active(*key)
                if session is not None:
                    self._save(
                        replace(
                            session,
                            status=SessionStatus.FAILED,
                            metadata={
                                **session.metadata,
                                "last_error": str(exc),
                                "last_error_type": type(exc).__name__,
                            },
                        ),
                        update=update,
                    )
                await self._events.emit(
                    "runtime.error",
                    str(exc),
                    level="error",
                    session_id=session.id if session else None,
                    entity_type="node" if session else None,
                    entity_id=session.current_node_id if session else None,
                    context={
                        "traceback": traceback.format_exc(),
                        "flow_id": session.flow_id if session else None,
                        "node_id": session.current_node_id if session else None,
                    },
                )
                raise

    async def _handle_locked(self, update: IncomingUpdate) -> Session | None:
        active = self._sessions.find_active(
            self.project.id,
            update.telegram_user_id,
            update.telegram_chat_id,
        )

        if update.is_start:
            if active is not None and self.project.configuration.start_behavior == "resume":
                flow = self._load_flow(active.flow_id)
                await self._events.emit(
                    "session.resumed",
                    "Existing session resumed by /start",
                    session_id=active.id,
                )
                return await self._execute(active, flow, None)

            if active is not None:
                self._save(
                    replace(
                        active,
                        status=SessionStatus.RESET,
                        waiting_for_input=None,
                    ),
                    update=update,
                )
                await self._events.emit(
                    "session.reset",
                    "Session reset by /start",
                    session_id=active.id,
                )

            flow = self._load_start_flow()
            start_node = self._start_node(flow)
            session = Session.create(
                project_id=self.project.id,
                telegram_user_id=update.telegram_user_id,
                telegram_chat_id=update.telegram_chat_id,
                flow_id=flow.id,
                current_node_id=start_node.id,
            )
            session = self._save(session, update=update)
            await self._events.emit(
                "session.started",
                "New session started",
                session_id=session.id,
                entity_type="flow",
                entity_id=flow.id,
            )
            return await self._execute(session, flow, None)

        if active is None:
            await self._telegram.send(
                OutboundMessage(
                    chat_id=update.telegram_chat_id,
                    text=str(
                        self.project.configuration.metadata.get(
                            "inactive_session_message",
                            "Send /start to begin.",
                        )
                    ),
                )
            )
            await self._events.emit(
                "update.ignored",
                "Update ignored because there is no active session",
                context={"telegram_user_id": update.telegram_user_id},
            )
            return None

        last_update_id = active.metadata.get("last_update_id")
        if update.update_id > 0 and isinstance(last_update_id, int) and update.update_id <= last_update_id:
            await self._events.emit(
                "update.duplicate",
                f"Duplicate update {update.update_id} ignored",
                session_id=active.id,
            )
            return active

        return await self._execute(active, self._load_flow(active.flow_id), update)

    async def _execute(
        self,
        session: Session,
        flow: Flow,
        update: IncomingUpdate | None,
    ) -> Session:
        pending_update = update
        for step_number in range(1, self._guard_limit + 1):
            node = self._node(flow, session.current_node_id)
            await self._events.emit(
                "node.entered",
                f"Entering {node.type.value} node '{node.name or node.id}'",
                session_id=session.id,
                entity_type="node",
                entity_id=node.id,
                context={"step": step_number, "node_type": node.type.value},
            )

            if node.type is NodeType.START:
                session = await self._advance(
                    session,
                    flow,
                    node,
                    kinds=(TransitionKind.AUTOMATIC,),
                    update=pending_update,
                )
                pending_update = None
                continue

            if node.type is NodeType.SEND_MESSAGE:
                if self._is_button_wait(session) and pending_update is not None:
                    session = await self._handle_button_input(
                        session, flow, node, pending_update
                    )
                    pending_update = None
                    continue

                await self._send_node_message(session, node)
                if self._has_outgoing(flow, node.id, TransitionKind.BUTTON):
                    session = self._save(
                        replace(
                            session,
                            status=SessionStatus.WAITING_INPUT,
                            waiting_for_input=InputExpectation(
                                variable_name="__button__",
                                expected_type=VariableType.STRING,
                                max_attempts=1,
                            ),
                        ),
                        update=pending_update,
                    )
                    return session

                session = await self._advance(
                    session,
                    flow,
                    node,
                    kinds=(TransitionKind.AUTOMATIC, TransitionKind.SUCCESS),
                    update=pending_update,
                )
                pending_update = None
                continue

            if node.type is NodeType.ASK_INPUT:
                session, should_continue = await self._handle_ask_input(
                    session, flow, node, pending_update
                )
                pending_update = None
                if should_continue:
                    continue
                return session

            if node.type is NodeType.CHOICE:
                session, should_continue = await self._handle_choice(
                    session, flow, node, pending_update
                )
                pending_update = None
                if should_continue:
                    continue
                return session

            if node.type is NodeType.CONDITION:
                outcome = self._condition_outcome(node.config, session.variables)
                session = await self._advance(
                    session,
                    flow,
                    node,
                    kinds=(TransitionKind.CONDITION,),
                    outcome="true" if outcome else "false",
                    update=pending_update,
                )
                pending_update = None
                continue

            if node.type is NodeType.ACTION:
                session = await self._handle_action(session, flow, node, pending_update)
                pending_update = None
                continue

            if node.type is NodeType.END:
                if any(
                    key in node.config
                    for key in ("text", "media", "photo", "document")
                ):
                    await self._send_node_message(session, node)
                session = self._save(
                    replace(
                        session,
                        status=SessionStatus.COMPLETED,
                        waiting_for_input=None,
                    ),
                    update=pending_update,
                )
                await self._events.emit(
                    "session.completed",
                    "Session completed",
                    session_id=session.id,
                    entity_type="node",
                    entity_id=node.id,
                )
                return session

            raise InvalidNodeConfigurationError(
                f"Unsupported node type '{node.type}'",
                context=self._context(session, flow, node),
            )

        raise ExecutionGuardError(
            f"Flow exceeded the limit of {self._guard_limit} automatic steps",
            context=RuntimeErrorContext(
                project_id=self.project.id,
                flow_id=flow.id,
                node_id=session.current_node_id,
                session_id=session.id,
            ),
        )

    async def _handle_ask_input(
        self,
        session: Session,
        flow: Flow,
        node: Node,
        update: IncomingUpdate | None,
    ) -> tuple[Session, bool]:
        config = node.config
        prompt = self._required_text(config, "prompt", fallback_key="text")
        variable_name = str(
            config.get("variable_name", config.get("variable", ""))
        ).strip()
        if not variable_name:
            raise InvalidNodeConfigurationError(
                "Ask Input node requires variable_name",
                context=self._context(session, flow, node),
            )

        expectation = session.waiting_for_input
        if expectation is None or expectation.variable_name != variable_name:
            expectation = InputExpectation(
                variable_name=variable_name,
                expected_type=self._variable_type(config),
                required=bool(config.get("required", True)),
                attempts=0,
                max_attempts=max(
                    1,
                    int(config.get("max_attempts", config.get("retries", 3))),
                ),
                error_message=(
                    str(config["error_message"])
                    if config.get("error_message") is not None
                    else None
                ),
            )
            await self._send_text(session, self._templates.render(prompt, session.variables))
            session = self._save(
                replace(
                    session,
                    status=SessionStatus.WAITING_INPUT,
                    waiting_for_input=expectation,
                ),
                update=update,
            )
            return session, False

        if update is None:
            await self._send_text(session, self._templates.render(prompt, session.variables))
            return self._save(session), False

        spec = {
            **config,
            "type": expectation.expected_type.value,
            "required": expectation.required,
            "error_message": expectation.error_message or config.get("error_message"),
        }
        result = self._inputs.validate(update.input_value, spec)
        if not result.accepted:
            attempts = expectation.attempts + 1
            error_text = result.error or "Invalid value."
            await self._send_text(session, error_text)

            if attempts >= expectation.max_attempts:
                try:
                    transition = self._resolve_first(
                        flow,
                        node.id,
                        kinds=(TransitionKind.ERROR,),
                    )
                except MissingTransitionError:
                    session = self._save(
                        replace(
                            session,
                            status=SessionStatus.FAILED,
                            waiting_for_input=None,
                            metadata={
                                **session.metadata,
                                "last_error": "Input attempts exhausted",
                            },
                        ),
                        update=update,
                    )
                    await self._events.emit(
                        "input.exhausted",
                        "Input attempts exhausted and no error transition is configured",
                        level="error",
                        session_id=session.id,
                        entity_type="node",
                        entity_id=node.id,
                    )
                    return session, False

                session = await self._apply_transition(
                    session, flow, node, transition, update=update
                )
                return session, True

            expectation = replace(expectation, attempts=attempts)
            await self._send_text(session, self._templates.render(prompt, session.variables))
            return (
                self._save(
                    replace(session, waiting_for_input=expectation),
                    update=update,
                ),
                False,
            )

        variables = dict(session.variables)
        variables[variable_name] = result.value
        session = replace(
            session,
            variables=variables,
            status=SessionStatus.ACTIVE,
            waiting_for_input=None,
        )
        transition = self._resolve_first(
            flow,
            node.id,
            kinds=(TransitionKind.INPUT, TransitionKind.SUCCESS, TransitionKind.AUTOMATIC),
        )
        session = await self._apply_transition(
            session, flow, node, transition, update=update
        )
        await self._events.emit(
            "input.accepted",
            f"Input stored in variable '{variable_name}'",
            session_id=session.id,
            entity_type="node",
            entity_id=node.id,
            context={"variable_name": variable_name},
        )
        return session, True

    async def _handle_choice(
        self,
        session: Session,
        flow: Flow,
        node: Node,
        update: IncomingUpdate | None,
    ) -> tuple[Session, bool]:
        choices = self._choices(flow, node)
        if not choices:
            raise InvalidNodeConfigurationError(
                "Choice node has no choices",
                context=self._context(session, flow, node),
            )

        if session.waiting_for_input is None:
            await self._send_choice(session, node, choices)
            variable_name = str(
                node.config.get("variable_name", node.config.get("variable", "__choice__"))
            )
            session = self._save(
                replace(
                    session,
                    status=SessionStatus.WAITING_INPUT,
                    waiting_for_input=InputExpectation(
                        variable_name=variable_name,
                        expected_type=VariableType.STRING,
                        max_attempts=max(1, int(node.config.get("max_attempts", 3))),
                    ),
                ),
                update=update,
            )
            return session, False

        if update is None:
            await self._send_choice(session, node, choices)
            return self._save(session), False

        raw_value = (update.input_value or "").strip()
        raw_value = self._callback_selector(raw_value)
        selected = self._match_choice(choices, raw_value)
        if selected is None:
            expectation = session.waiting_for_input
            attempts = (expectation.attempts if expectation else 0) + 1
            await self._send_text(
                session,
                str(node.config.get("error_message", "Please choose one of the available options.")),
            )
            if expectation and attempts >= expectation.max_attempts:
                transition = self._resolve_first(
                    flow, node.id, kinds=(TransitionKind.ERROR,)
                )
                session = await self._apply_transition(
                    replace(session, waiting_for_input=None, status=SessionStatus.ACTIVE),
                    flow,
                    node,
                    transition,
                    update=update,
                )
                return session, True
            if expectation:
                session = self._save(
                    replace(session, waiting_for_input=replace(expectation, attempts=attempts)),
                    update=update,
                )
            return session, False

        value = str(selected["value"])
        variable_name = session.waiting_for_input.variable_name
        variables = dict(session.variables)
        if variable_name and not variable_name.startswith("__"):
            variables[variable_name] = value

        transition_outcome = str(selected.get("transition") or value)
        transition = self._resolve_first(
            flow,
            node.id,
            kinds=(TransitionKind.BUTTON, TransitionKind.INPUT),
            outcome=transition_outcome,
        )
        session = await self._apply_transition(
            replace(
                session,
                variables=variables,
                status=SessionStatus.ACTIVE,
                waiting_for_input=None,
            ),
            flow,
            node,
            transition,
            update=update,
        )
        return session, True

    async def _handle_button_input(
        self,
        session: Session,
        flow: Flow,
        node: Node,
        update: IncomingUpdate,
    ) -> Session:
        value = (update.input_value or "").strip()
        value = self._callback_selector(value)
        transition = self._resolve_first(
            flow,
            node.id,
            kinds=(TransitionKind.BUTTON,),
            outcome=value,
        )
        return await self._apply_transition(
            replace(session, status=SessionStatus.ACTIVE, waiting_for_input=None),
            flow,
            node,
            transition,
            update=update,
        )

    async def _handle_action(
        self,
        session: Session,
        flow: Flow,
        node: Node,
        update: IncomingUpdate | None,
    ) -> Session:
        action_name = str(
            node.config.get("action_name", node.config.get("action", ""))
        ).strip()
        if not action_name:
            raise InvalidNodeConfigurationError(
                "Action node requires action_name",
                context=self._context(session, flow, node),
            )
        timeout_seconds = float(node.config.get("timeout_seconds", 30.0))
        raw_parameters = node.config.get("input_parameters", {})
        if not isinstance(raw_parameters, Mapping):
            raise InvalidNodeConfigurationError(
                "Action input_parameters must be an object",
                context=self._context(session, flow, node),
            )
        parameters = self._render_value(raw_parameters, session.variables)
        try:
            result = await self._actions.invoke(
                project=self.project,
                project_root=self.project_root,
                session=session,
                update=update,
                action_name=action_name,
                timeout_seconds=timeout_seconds,
                parameters=dict(parameters),
                flow_id=flow.id,
                node_id=node.id,
            )
        except ActionExecutionError as exc:
            try:
                error_transition = self._resolve_first(
                    flow,
                    node.id,
                    kinds=(TransitionKind.ERROR,),
                    outcome="error",
                )
            except MissingTransitionError:
                try:
                    error_transition = self._resolve_first(
                        flow,
                        node.id,
                        kinds=(TransitionKind.ERROR,),
                    )
                except MissingTransitionError:
                    raise exc
            failed = replace(
                session,
                metadata={
                    **session.metadata,
                    "last_action_error": str(exc),
                    "last_action_traceback": (
                        exc.context.details or {}
                    ).get("traceback"),
                },
            )
            return await self._apply_transition(
                failed,
                flow,
                node,
                error_transition,
                update=update,
            )

        variables = dict(session.variables)
        mapping = node.config.get("output_mapping")
        if isinstance(mapping, Mapping):
            for result_key, variable_name in mapping.items():
                if result_key in result.variables and variable_name:
                    variables[str(variable_name)] = result.variables[result_key]
        else:
            variables.update(result.variables)
        session = replace(session, variables=variables)

        if result.status is ActionResultStatus.ERROR:
            kinds = (TransitionKind.ERROR,)
            outcome = result.next_transition
        elif result.status is ActionResultStatus.BRANCH:
            kinds = (TransitionKind.ACTION, TransitionKind.SUCCESS)
            outcome = result.next_transition
        else:
            kinds = (TransitionKind.SUCCESS, TransitionKind.ACTION, TransitionKind.AUTOMATIC)
            outcome = result.next_transition

        transition = self._resolve_first(
            flow,
            node.id,
            kinds=kinds,
            outcome=outcome,
        )
        session = await self._apply_transition(
            session, flow, node, transition, update=update
        )
        await self._events.emit(
            "action.completed",
            f"Action '{action_name}' returned {result.status.value}",
            level="error" if result.status is ActionResultStatus.ERROR else "info",
            session_id=session.id,
            entity_type="action",
            entity_id=action_name,
            context={
                "status": result.status.value,
                "transition": result.next_transition,
                "error": result.error,
                "flow_id": flow.id,
                "node_id": node.id,
            },
        )
        return session

    async def _advance(
        self,
        session: Session,
        flow: Flow,
        node: Node,
        *,
        kinds: Sequence[TransitionKind],
        update: IncomingUpdate | None,
        outcome: str | None = None,
    ) -> Session:
        transition = self._resolve_first(
            flow, node.id, kinds=kinds, outcome=outcome
        )
        return await self._apply_transition(
            session, flow, node, transition, update=update
        )

    async def _apply_transition(
        self,
        session: Session,
        flow: Flow,
        node: Node,
        transition: Transition,
        *,
        update: IncomingUpdate | None,
    ) -> Session:
        session = self._save(
            replace(
                session,
                current_node_id=transition.target_node_id,
                status=SessionStatus.ACTIVE,
                waiting_for_input=None,
            ),
            update=update,
        )
        await self._events.emit(
            "transition.followed",
            f"Transition '{transition.id}' followed",
            session_id=session.id,
            entity_type="transition",
            entity_id=transition.id,
            context={
                "flow_id": flow.id,
                "source_node_id": node.id,
                "target_node_id": transition.target_node_id,
                "kind": transition.kind.value,
            },
        )
        return session

    def _resolve_first(
        self,
        flow: Flow,
        node_id: str,
        *,
        kinds: Sequence[TransitionKind],
        outcome: str | None = None,
    ) -> Transition:
        last_error: MissingTransitionError | None = None
        for kind in kinds:
            try:
                return self._transitions.resolve(
                    flow,
                    node_id,
                    kinds=(kind,),
                    outcome=outcome,
                )
            except MissingTransitionError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def _send_node_message(self, session: Session, node: Node) -> None:
        config = node.config
        text_template = str(config.get("text", ""))
        text = self._templates.render(text_template, session.variables) if text_template else None
        keyboard = self._build_keyboard(config, session.variables)

        media_kind: MediaKind | None = None
        media: str | bytes | None = None
        raw_media = config.get("media")
        if isinstance(raw_media, Mapping):
            kind = raw_media.get("type", raw_media.get("kind"))
            source = raw_media.get("source", raw_media.get("path", raw_media.get("url")))
            if kind and source is not None:
                media_kind = MediaKind(str(kind))
                rendered_source = self._templates.render(str(source), session.variables)
                media = self._resolve_media_source(
                    rendered_source,
                    source_type=str(raw_media.get("source_type", "")),
                )
        elif config.get("photo") is not None:
            media_kind = MediaKind.PHOTO
            rendered_source = self._templates.render(str(config["photo"]), session.variables)
            media = self._resolve_media_source(rendered_source)
        elif config.get("document") is not None:
            media_kind = MediaKind.DOCUMENT
            rendered_source = self._templates.render(str(config["document"]), session.variables)
            media = self._resolve_media_source(rendered_source)

        if text is None and media is None:
            raise InvalidNodeConfigurationError(
                "Send Message node requires text or media",
                context=RuntimeErrorContext(
                    project_id=self.project.id,
                    node_id=node.id,
                    session_id=session.id,
                ),
            )

        await self._telegram.send(
            OutboundMessage(
                chat_id=session.telegram_chat_id,
                text=text if media is None else None,
                caption=text if media is not None else None,
                parse_mode=config.get("parse_mode"),
                keyboard=keyboard,
                media_kind=media_kind,
                media=media,
            )
        )

    async def _send_choice(
        self,
        session: Session,
        node: Node,
        choices: Sequence[dict[str, Any]],
    ) -> None:
        prompt = self._required_text(node.config, "prompt", fallback_key="text")
        keyboard_kind = KeyboardKind(
            str(node.config.get("keyboard_type", "inline")).casefold()
        )
        columns = max(1, int(node.config.get("columns", 1)))
        buttons = [
            KeyboardButton(
                text=self._templates.render(str(choice["label"]), session.variables),
                value=(
                    self._choice_callback(
                        str(
                            choice.get("id")
                            or choice.get("transition")
                            or choice["value"]
                        )
                    )
                    if keyboard_kind is KeyboardKind.INLINE
                    else str(choice["value"])
                ),
            )
            for choice in choices
        ]
        rows = tuple(
            tuple(buttons[index : index + columns])
            for index in range(0, len(buttons), columns)
        )
        await self._telegram.send(
            OutboundMessage(
                chat_id=session.telegram_chat_id,
                text=self._templates.render(prompt, session.variables),
                keyboard=Keyboard(kind=keyboard_kind, rows=rows),
            )
        )

    async def _send_text(self, session: Session, text: str) -> None:
        await self._telegram.send(
            OutboundMessage(chat_id=session.telegram_chat_id, text=text)
        )

    def _build_keyboard(
        self,
        config: Mapping[str, Any],
        variables: Mapping[str, Any],
    ) -> Keyboard | None:
        raw = config.get("keyboard", config.get("buttons"))
        if raw is None:
            return None
        if isinstance(raw, Mapping):
            raw_rows = raw.get("rows", raw.get("buttons", ()))
            kind = KeyboardKind(str(raw.get("type", "inline")).casefold())
            resize = bool(raw.get("resize", True))
            one_time = bool(raw.get("one_time", False))
        else:
            raw_rows = raw
            kind = KeyboardKind.INLINE
            resize = True
            one_time = False

        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
            raise InvalidNodeConfigurationError("Keyboard rows must be a list")
        if raw_rows and (
            not isinstance(raw_rows[0], Sequence)
            or isinstance(raw_rows[0], (str, bytes))
        ):
            raw_rows = [[item] for item in raw_rows]

        rows: list[tuple[KeyboardButton, ...]] = []
        for raw_row in raw_rows:
            row: list[KeyboardButton] = []
            for raw_button in raw_row:
                if isinstance(raw_button, str):
                    label = self._templates.render(raw_button, variables)
                    row.append(KeyboardButton(text=label, value=label))
                    continue
                if not isinstance(raw_button, Mapping):
                    raise InvalidNodeConfigurationError("Keyboard button must be a string or object")
                label = self._templates.render(str(raw_button.get("text", "")), variables)
                value = raw_button.get("callback_data", raw_button.get("value", label))
                url = raw_button.get("url")
                rendered_value = (
                    self._templates.render(str(value), variables)
                    if value is not None
                    else None
                )
                if kind is KeyboardKind.INLINE and rendered_value is not None and url is None:
                    rendered_value = self._flow_callback(rendered_value)
                row.append(
                    KeyboardButton(
                        text=label,
                        value=rendered_value,
                        url=self._templates.render(str(url), variables) if url is not None else None,
                    )
                )
            if row:
                rows.append(tuple(row))
        return Keyboard(kind=kind, rows=tuple(rows), resize=resize, one_time=one_time)

    def _choices(self, flow: Flow, node: Node) -> tuple[dict[str, Any], ...]:
        raw_choices = node.config.get("choices", node.config.get("options"))
        choices: list[dict[str, Any]] = []
        if isinstance(raw_choices, Sequence) and not isinstance(raw_choices, (str, bytes)):
            for raw in raw_choices:
                if isinstance(raw, str):
                    choices.append({"label": raw, "value": raw})
                elif isinstance(raw, Mapping):
                    label = raw.get("label", raw.get("text", raw.get("value")))
                    value = raw.get("value", raw.get("callback_data", label))
                    if label is not None and value is not None:
                        choice_id = raw.get("id")
                        normalized_choice_id = (
                            str(choice_id) if choice_id is not None else None
                        )
                        choice_selector = (
                            normalized_choice_id
                            if normalized_choice_id
                            and normalized_choice_id.startswith("option-")
                            else (
                                f"option-{normalized_choice_id}"
                                if normalized_choice_id
                                else None
                            )
                        )
                        transition_selector = (
                            raw.get("transition")
                            or raw.get("outcome")
                            or raw.get("source_handle")
                            or choice_selector
                            or value
                        )
                        choices.append(
                            {
                                "label": str(label),
                                "value": str(value),
                                "id": str(choice_id) if choice_id is not None else None,
                                "transition": str(transition_selector),
                            }
                        )
        if choices:
            return tuple(choices)

        for transition in self._transitions.outgoing(flow, node.id):
            if transition.kind is not TransitionKind.BUTTON:
                continue
            value = transition.outcome or transition.label
            if value:
                choices.append(
                    {
                        "label": transition.label or value,
                        "value": value,
                        "transition": value,
                    }
                )
        return tuple(choices)

    @staticmethod
    def _match_choice(
        choices: Sequence[dict[str, Any]], raw_value: str
    ) -> dict[str, Any] | None:
        normalized = raw_value.casefold()
        for choice in choices:
            values = {
                str(choice.get("value", "")).casefold(),
                str(choice.get("label", "")).casefold(),
                str(choice.get("transition", "")).casefold(),
                str(choice.get("id", "")).casefold(),
            }
            if normalized in values:
                return choice
        return None

    def _render_value(
        self,
        value: Any,
        variables: Mapping[str, Any],
    ) -> Any:
        if isinstance(value, str):
            return self._templates.render(value, variables)
        if isinstance(value, Mapping):
            return {
                str(key): self._render_value(item, variables)
                for key, item in value.items()
            }
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [self._render_value(item, variables) for item in value]
        return value

    @staticmethod
    def _choice_callback(value: str) -> str:
        callback = GraphExecutor._flow_callback(value)
        return callback

    @staticmethod
    def _flow_callback(value: str) -> str:
        if value.startswith(("svc:", "st:")):
            callback = value
        else:
            callback = f"svc:flow:{value}"
        if len(callback.encode("utf-8")) > 64:
            raise InvalidNodeConfigurationError(
                "Callback exceeds Telegram's 64-byte limit"
            )
        return callback

    @staticmethod
    def _callback_selector(value: str) -> str:
        for prefix in ("svc:flow:", "choice:"):
            if value.startswith(prefix):
                return value.removeprefix(prefix)
        return value

    def _resolve_media_source(
        self,
        source: str,
        *,
        source_type: str = "",
    ) -> str:
        normalized_type = source_type.casefold()
        if normalized_type in {"file_id", "url"} or source.startswith(("http://", "https://")):
            return source
        assets_root = (self.project_root / "assets").resolve()
        relative = source.replace("\\", "/")
        if relative.startswith("assets/"):
            relative = relative.removeprefix("assets/")
        candidate = (assets_root / relative).resolve()
        try:
            candidate.relative_to(assets_root)
        except ValueError as exc:
            raise InvalidNodeConfigurationError(
                f"Media path escapes the project assets directory: {source}"
            ) from exc
        if candidate.is_file():
            return str(candidate)
        if normalized_type == "asset" or "/" in relative:
            raise InvalidNodeConfigurationError(f"Media asset does not exist: {source}")
        # Telegram file_id values are opaque and may look like a simple filename.
        return source

    def _condition_outcome(
        self,
        config: Mapping[str, Any],
        variables: Mapping[str, Any],
    ) -> bool:
        if isinstance(config.get("all"), Sequence):
            return all(
                self._conditions.evaluate(item, variables)
                for item in config["all"]
                if isinstance(item, Mapping)
            )
        if isinstance(config.get("any"), Sequence):
            return any(
                self._conditions.evaluate(item, variables)
                for item in config["any"]
                if isinstance(item, Mapping)
            )
        expression = config.get("condition", config)
        if not isinstance(expression, Mapping):
            raise InvalidNodeConfigurationError("Condition config must be an object")
        return self._conditions.evaluate(expression, variables)

    def _load_start_flow(self) -> Flow:
        flow_id = self.project.configuration.start_flow_id
        if not flow_id:
            raise FlowNotFoundError(
                "Project has no configured start_flow_id",
                context=RuntimeErrorContext(project_id=self.project.id),
            )
        return self._load_flow(flow_id)

    def _load_flow(self, flow_id: str) -> Flow:
        try:
            return self._projects.load_flow(self.project_root, flow_id)
        except Exception as exc:
            raise FlowNotFoundError(
                f"Cannot load flow '{flow_id}': {exc}",
                context=RuntimeErrorContext(
                    project_id=self.project.id,
                    flow_id=flow_id,
                ),
            ) from exc

    @staticmethod
    def _start_node(flow: Flow) -> Node:
        if flow.start_node_id:
            for node in flow.nodes:
                if node.id == flow.start_node_id:
                    return node
            raise NodeNotFoundError(
                f"Configured start node '{flow.start_node_id}' does not exist"
            )
        starts = [node for node in flow.nodes if node.type is NodeType.START]
        if len(starts) != 1:
            raise InvalidNodeConfigurationError(
                f"Flow '{flow.id}' must have exactly one Start node; found {len(starts)}"
            )
        return starts[0]

    @staticmethod
    def _node(flow: Flow, node_id: str) -> Node:
        for node in flow.nodes:
            if node.id == node_id:
                return node
        raise NodeNotFoundError(
            f"Node '{node_id}' does not exist in flow '{flow.id}'",
            context=RuntimeErrorContext(flow_id=flow.id, node_id=node_id),
        )

    def _save(
        self,
        session: Session,
        *,
        update: IncomingUpdate | None = None,
    ) -> Session:
        metadata = dict(session.metadata)
        if update is not None and update.update_id > 0:
            metadata["last_update_id"] = update.update_id
        saved = replace(session, metadata=metadata, updated_at=utc_now())
        self._sessions.save(saved)
        return saved

    def _has_outgoing(self, flow: Flow, node_id: str, kind: TransitionKind) -> bool:
        return any(
            transition.kind is kind
            for transition in self._transitions.outgoing(flow, node_id)
        )

    @staticmethod
    def _is_button_wait(session: Session) -> bool:
        return bool(
            session.waiting_for_input
            and session.waiting_for_input.variable_name == "__button__"
        )

    @staticmethod
    def _required_text(
        config: Mapping[str, Any],
        key: str,
        *,
        fallback_key: str,
    ) -> str:
        value = config.get(key, config.get(fallback_key))
        if not isinstance(value, str) or not value:
            raise InvalidNodeConfigurationError(
                f"Node requires non-empty '{key}'"
            )
        return value

    @staticmethod
    def _variable_type(config: Mapping[str, Any]) -> VariableType:
        raw = config.get(
            "input_type",
            config.get("expected_type", config.get("type", VariableType.STRING.value)),
        )
        try:
            return VariableType(str(raw).casefold())
        except ValueError as exc:
            raise InvalidNodeConfigurationError(
                f"Unsupported input type '{raw}'"
            ) from exc

    def _context(self, session: Session, flow: Flow, node: Node) -> RuntimeErrorContext:
        return RuntimeErrorContext(
            project_id=self.project.id,
            flow_id=flow.id,
            node_id=node.id,
            session_id=session.id,
        )
