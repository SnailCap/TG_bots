from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..content import BotContentDocument


SCHEMA_VERSION = 3
HANDLER_KINDS = frozenset({"button", "message", "command", "lifecycle", "task"})
ACTION_TYPES = frozenset(
    {
        "noop",
        "view.render",
        "flow.start",
        "flow.cancel",
        "flow.event",
        "flow.goto",
        "flow.finish",
        "handler.invoke",
        "task.enqueue",
    }
)


@dataclass(frozen=True, slots=True)
class Diagnostic:
    level: str
    code: str
    message: str
    source_path: str | None = None
    entity_id: str | None = None
    field_path: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            **({"source_path": self.source_path} if self.source_path else {}),
            **({"entity_id": self.entity_id} if self.entity_id else {}),
            **({"field_path": self.field_path} if self.field_path else {}),
        }


@dataclass(frozen=True, slots=True)
class ActionSpec:
    type: str
    target: str | None = None
    handler: str | None = None
    outcomes: Mapping[str, "ActionSpec"] = field(default_factory=dict)
    payload: Mapping[str, Any] = field(default_factory=dict)
    delay_seconds: float = 0
    view: str | None = None
    delivery: str = "edit"


@dataclass(frozen=True, slots=True)
class HandlerInvocation:
    handler: str
    outcomes: Mapping[str, ActionSpec] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TextSpec:
    inline: str | None = None
    template: str | None = None
    document: str | None = None


@dataclass(frozen=True, slots=True)
class ButtonSpec:
    id: str
    text: str
    action: ActionSpec


@dataclass(frozen=True, slots=True)
class ViewSpec:
    id: str
    text: TextSpec
    keyboard: tuple[tuple[ButtonSpec, ...], ...] = ()
    source_path: str | None = None


@dataclass(frozen=True, slots=True)
class StateSpec:
    id: str
    view: str
    on_enter: HandlerInvocation | None = None
    on_message: HandlerInvocation | None = None
    events: Mapping[str, HandlerInvocation] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FlowLifecycle:
    on_start: HandlerInvocation | None = None
    on_complete: HandlerInvocation | None = None
    on_cancel: HandlerInvocation | None = None
    on_error: HandlerInvocation | None = None


@dataclass(frozen=True, slots=True)
class FlowSpec:
    id: str
    initial_state: str
    states: Mapping[str, StateSpec]
    lifecycle: FlowLifecycle = field(default_factory=FlowLifecycle)
    source_path: str | None = None


@dataclass(frozen=True, slots=True)
class HandlerBinding:
    id: str
    module: str
    symbol: str
    kind: str
    outcomes: tuple[str, ...] = ()
    description: str | None = None
    source_path: str | None = None


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    description: str | None
    action: ActionSpec


@dataclass(frozen=True, slots=True)
class CommandsSpec:
    commands: tuple[CommandSpec, ...] = ()
    message_fallback: ActionSpec | None = None
    command_fallback: ActionSpec | None = None


@dataclass(frozen=True, slots=True)
class ScheduleTrigger:
    type: str
    seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ScheduleSpec:
    id: str
    handler: str
    trigger: ScheduleTrigger
    payload: Mapping[str, Any] = field(default_factory=dict)
    source_path: str | None = None


@dataclass(frozen=True, slots=True)
class StartSpec:
    flow: str
    policy: str = "reset"


@dataclass(frozen=True, slots=True)
class BotManifest:
    id: str
    package: str
    entry_view: str
    start: StartSpec
    # Studio-only presentation metadata. It deliberately does not affect
    # runtime dispatch: all graph references continue to use technical ids.
    display_names: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ProjectDefinition:
    root: Path
    resources: Path
    manifest: BotManifest
    views: Mapping[str, ViewSpec]
    flows: Mapping[str, FlowSpec]
    handlers: Mapping[str, HandlerBinding]
    commands: CommandsSpec
    schedules: Mapping[str, ScheduleSpec]
    templates: Mapping[str, str]
    content_documents: Mapping[str, BotContentDocument] = field(default_factory=dict)

    @property
    def actions(self) -> Mapping[str, ActionSpec]:
        return {
            button.id: button.action
            for view in self.views.values()
            for row in view.keyboard
            for button in row
        }
