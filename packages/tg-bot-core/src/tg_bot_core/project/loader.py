from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping

from .models import (
    SCHEMA_VERSION,
    ActionSpec,
    BotManifest,
    ButtonSpec,
    CommandSpec,
    CommandsSpec,
    FlowLifecycle,
    FlowSpec,
    HandlerBinding,
    HandlerInvocation,
    ProjectDefinition,
    ScheduleSpec,
    ScheduleTrigger,
    StartSpec,
    StateSpec,
    TextSpec,
    ViewSpec,
)


class ProjectLoadError(RuntimeError):
    """The on-disk project cannot be parsed."""


class ProjectLoader:
    """Load an autonomous project without importing any custom Python code."""

    def load(self, root: str | Path) -> ProjectDefinition:
        candidate = Path(root).resolve()
        nested_resources = candidate / "resources"
        if (nested_resources / "bot.json").is_file():
            resources = nested_resources
        elif (candidate / "bot.json").is_file():
            resources = candidate
        else:
            resources = nested_resources
        project_root = resources.parent
        if not resources.is_dir():
            raise ProjectLoadError(f"Project resources directory does not exist: {resources}")

        manifest = self._manifest(self._object(resources / "bot.json"), "bot.json")
        views = self._load_directory(resources, "views", self._view)
        flows = self._load_directory(resources, "flows", self._flow)
        schedules = self._load_directory(resources, "schedules", self._schedule)
        handlers = self._handlers(self._object(resources / "handlers.json"), "handlers.json")
        commands = self._commands(self._object(resources / "commands.json"), "commands.json")
        templates_dir = resources / "templates"
        if not templates_dir.is_dir():
            raise ProjectLoadError("resources/templates is required.")
        templates = {
            path.relative_to(templates_dir).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(templates_dir.rglob("*.txt"))
        }
        return ProjectDefinition(
            root=project_root,
            resources=resources,
            manifest=manifest,
            views=views,
            flows=flows,
            handlers=handlers,
            commands=commands,
            schedules=schedules,
            templates=templates,
        )

    def _load_directory(self, resources: Path, name: str, parser):
        directory = resources / name
        if not directory.is_dir():
            raise ProjectLoadError(f"resources/{name} is required.")
        result: dict[str, Any] = {}
        for path in sorted(directory.rglob("*.json")):
            source = path.relative_to(resources).as_posix()
            value = parser(self._object(path), source)
            if value.id in result:
                raise ProjectLoadError(f"Duplicate {name[:-1]} id '{value.id}'.")
            result[value.id] = value
        return result

    def _manifest(self, data: Mapping[str, Any], source: str) -> BotManifest:
        self._version(data, source)
        start = self._mapping(data.get("start"), source, "start")
        policy = start.get("policy", "reset")
        if policy not in {"reset", "resume"}:
            raise ProjectLoadError(f"{source}: start.policy must be 'reset' or 'resume'.")
        return BotManifest(
            id=self._string(data, "id", source),
            package=self._string(data, "package", source),
            entry_view=self._string(data, "entry_view", source),
            start=StartSpec(self._string(start, "flow", source), policy),
        )

    def _view(self, data: Mapping[str, Any], source: str) -> ViewSpec:
        self._version(data, source)
        text = self._mapping(data.get("text"), source, "text")
        inline, template = text.get("inline"), text.get("template")
        if (isinstance(inline, str)) == (isinstance(template, str)):
            raise ProjectLoadError(f"{source}: text must contain exactly one of inline or template.")
        rows = data.get("keyboard", [])
        if not isinstance(rows, list):
            raise ProjectLoadError(f"{source}: keyboard must be an array.")
        keyboard: list[tuple[ButtonSpec, ...]] = []
        for row_index, row in enumerate(rows):
            if not isinstance(row, list):
                raise ProjectLoadError(f"{source}: keyboard[{row_index}] must be an array.")
            buttons: list[ButtonSpec] = []
            for index, raw in enumerate(row):
                button = self._mapping(raw, source, f"keyboard[{row_index}][{index}]")
                buttons.append(
                    ButtonSpec(
                        id=self._string(button, "id", source),
                        text=self._string(button, "text", source),
                        action=self._action(button.get("action"), source, f"keyboard[{row_index}][{index}].action"),
                    )
                )
            keyboard.append(tuple(buttons))
        return ViewSpec(
            id=self._string(data, "id", source),
            text=TextSpec(inline=inline if isinstance(inline, str) else None, template=template if isinstance(template, str) else None),
            keyboard=tuple(keyboard),
            source_path=source,
        )

    def _flow(self, data: Mapping[str, Any], source: str) -> FlowSpec:
        self._version(data, source)
        raw_states = self._mapping(data.get("states"), source, "states")
        states: dict[str, StateSpec] = {}
        for state_id, raw in raw_states.items():
            state = self._mapping(raw, source, f"states.{state_id}")
            events_raw = state.get("events", {})
            events = {
                event_id: self._invocation(value, source, f"states.{state_id}.events.{event_id}")
                for event_id, value in self._mapping(events_raw, source, f"states.{state_id}.events").items()
            }
            states[state_id] = StateSpec(
                id=state_id,
                view=self._string(state, "view", source),
                on_enter=self._optional_invocation(state.get("on_enter"), source, f"states.{state_id}.on_enter"),
                on_message=self._optional_invocation(state.get("on_message"), source, f"states.{state_id}.on_message"),
                events=events,
            )
        lifecycle_raw = self._mapping(data.get("lifecycle", {}), source, "lifecycle")
        lifecycle = FlowLifecycle(
            on_start=self._optional_invocation(lifecycle_raw.get("on_start"), source, "lifecycle.on_start"),
            on_complete=self._optional_invocation(lifecycle_raw.get("on_complete"), source, "lifecycle.on_complete"),
            on_cancel=self._optional_invocation(lifecycle_raw.get("on_cancel"), source, "lifecycle.on_cancel"),
            on_error=self._optional_invocation(lifecycle_raw.get("on_error"), source, "lifecycle.on_error"),
        )
        return FlowSpec(
            id=self._string(data, "id", source),
            initial_state=self._string(data, "initial_state", source),
            states=states,
            lifecycle=lifecycle,
            source_path=source,
        )

    def _handlers(self, data: Mapping[str, Any], source: str) -> dict[str, HandlerBinding]:
        self._version(data, source)
        values = data.get("handlers", [])
        if not isinstance(values, list):
            raise ProjectLoadError(f"{source}: handlers must be an array.")
        result: dict[str, HandlerBinding] = {}
        for index, raw in enumerate(values):
            value = self._mapping(raw, source, f"handlers[{index}]")
            handler_id = self._string(value, "id", source)
            outcomes = value.get("outcomes", [])
            if not isinstance(outcomes, list) or not all(isinstance(item, str) for item in outcomes):
                raise ProjectLoadError(f"{source}: handler outcomes must be strings.")
            if handler_id in result:
                raise ProjectLoadError(f"Duplicate handler id '{handler_id}'.")
            result[handler_id] = HandlerBinding(
                id=handler_id,
                module=self._string(value, "module", source),
                symbol=self._string(value, "symbol", source),
                kind=self._string(value, "kind", source),
                outcomes=tuple(outcomes),
                description=value.get("description") if isinstance(value.get("description"), str) else None,
                source_path=source,
            )
        return result

    def _commands(self, data: Mapping[str, Any], source: str) -> CommandsSpec:
        self._version(data, source)
        values = data.get("commands", [])
        if not isinstance(values, list):
            raise ProjectLoadError(f"{source}: commands must be an array.")
        commands: list[CommandSpec] = []
        for index, raw in enumerate(values):
            value = self._mapping(raw, source, f"commands[{index}]")
            commands.append(
                CommandSpec(
                    name=self._string(value, "name", source).removeprefix("/"),
                    description=value.get("description") if isinstance(value.get("description"), str) else None,
                    action=self._action(value.get("action"), source, f"commands[{index}].action"),
                )
            )
        return CommandsSpec(
            commands=tuple(commands),
            message_fallback=self._optional_action(data.get("message_fallback"), source, "message_fallback"),
            command_fallback=self._optional_action(data.get("command_fallback"), source, "command_fallback"),
        )

    def _schedule(self, data: Mapping[str, Any], source: str) -> ScheduleSpec:
        self._version(data, source)
        trigger = self._mapping(data.get("trigger"), source, "trigger")
        seconds = trigger.get("seconds")
        normalized_seconds = self._finite_number(
            seconds,
            source,
            "trigger.seconds",
            optional=True,
        )
        payload = data.get("payload", {})
        return ScheduleSpec(
            id=self._string(data, "id", source),
            handler=self._string(data, "handler", source),
            trigger=ScheduleTrigger(self._string(trigger, "type", source), normalized_seconds),
            payload=self._mapping(payload, source, "payload"),
            source_path=source,
        )

    def _invocation(self, raw: Any, source: str, field: str) -> HandlerInvocation:
        value = self._mapping(raw, source, field)
        outcomes_raw = self._mapping(value.get("outcomes", {}), source, f"{field}.outcomes")
        return HandlerInvocation(
            handler=self._string(value, "handler", source),
            outcomes={name: self._action(action, source, f"{field}.outcomes.{name}") for name, action in outcomes_raw.items()},
        )

    def _optional_invocation(self, raw: Any, source: str, field: str) -> HandlerInvocation | None:
        return None if raw is None else self._invocation(raw, source, field)

    def _action(self, raw: Any, source: str, field: str) -> ActionSpec:
        value = self._mapping(raw, source, field)
        action_type = self._string(value, "type", source)
        fields_by_type = {
            "noop": {"type"},
            "view.render": {"type", "target"},
            "flow.start": {"type", "target"},
            "flow.cancel": {"type", "view"},
            "flow.event": {"type", "target"},
            "flow.goto": {"type", "target"},
            "flow.finish": {"type", "view"},
            "handler.invoke": {"type", "handler", "outcomes", "payload"},
            "task.enqueue": {"type", "target", "payload", "delay_seconds", "view"},
        }
        allowed = fields_by_type.get(action_type)
        if allowed is not None:
            unexpected = set(value) - allowed
            if unexpected:
                raise ProjectLoadError(f"{source}: {field} has unsupported fields for {action_type}: {', '.join(sorted(unexpected))}.")
        for optional_string in ("target", "handler", "view"):
            if optional_string in value and not isinstance(value[optional_string], str):
                raise ProjectLoadError(f"{source}: {field}.{optional_string} must be a string.")
        outcomes_raw = self._mapping(value.get("outcomes", {}), source, f"{field}.outcomes")
        delay = value.get("delay_seconds", 0)
        normalized_delay = self._finite_number(delay, source, f"{field}.delay_seconds")
        return ActionSpec(
            type=action_type,
            target=value.get("target") if isinstance(value.get("target"), str) else None,
            handler=value.get("handler") if isinstance(value.get("handler"), str) else None,
            outcomes={name: self._action(action, source, f"{field}.outcomes.{name}") for name, action in outcomes_raw.items()},
            payload=self._mapping(value.get("payload", {}), source, f"{field}.payload"),
            delay_seconds=normalized_delay,
            view=value.get("view") if isinstance(value.get("view"), str) else None,
        )

    def _optional_action(self, raw: Any, source: str, field: str) -> ActionSpec | None:
        return None if raw is None else self._action(raw, source, field)

    @staticmethod
    def _object(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(
                path.read_text(encoding="utf-8"),
                parse_constant=lambda constant: (_ for _ in ()).throw(
                    ValueError(f"non-finite JSON number '{constant}'")
                ),
            )
        except (OSError, ValueError) as error:
            raise ProjectLoadError(f"Cannot read JSON resource '{path}': {error}") from error
        if not isinstance(value, dict):
            raise ProjectLoadError(f"JSON resource must be an object: {path}")
        return value

    @staticmethod
    def _mapping(value: Any, source: str, field: str) -> Mapping[str, Any]:
        if not isinstance(value, dict):
            raise ProjectLoadError(f"{source}: {field} must be an object.")
        return value

    @staticmethod
    def _string(data: Mapping[str, Any], key: str, source: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ProjectLoadError(f"{source}: {key} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _version(data: Mapping[str, Any], source: str) -> None:
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ProjectLoadError(f"{source}: schema_version must be {SCHEMA_VERSION}.")

    @staticmethod
    def _finite_number(
        value: Any,
        source: str,
        field: str,
        *,
        optional: bool = False,
    ) -> float | None:
        if value is None and optional:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProjectLoadError(f"{source}: {field} must be a finite number.")
        try:
            normalized = float(value)
        except (OverflowError, ValueError) as error:
            raise ProjectLoadError(f"{source}: {field} must be a finite number.") from error
        if not math.isfinite(normalized):
            raise ProjectLoadError(f"{source}: {field} must be a finite number.")
        return normalized
