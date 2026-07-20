from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .models import ActionSpec, HandlerInvocation, ProjectDefinition


@dataclass(frozen=True, slots=True)
class HandlerUsage:
    handler_id: str
    entity_type: str
    entity_id: str
    field_path: str
    source_path: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            "handler_id": self.handler_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "field_path": self.field_path,
            **({"source_path": self.source_path} if self.source_path else {}),
        }


def find_handler_usages(project: ProjectDefinition, handler_id: str | None = None) -> list[HandlerUsage]:
    usages = list(_iter_handler_usages(project))
    return [usage for usage in usages if handler_id is None or usage.handler_id == handler_id]


def _iter_handler_usages(project: ProjectDefinition) -> Iterator[HandlerUsage]:
    for view in project.views.values():
        for row_index, row in enumerate(view.keyboard):
            for button_index, button in enumerate(row):
                yield from _action_usages(
                    button.action,
                    "view_button",
                    button.id,
                    f"keyboard.{row_index}.{button_index}.action",
                    view.source_path,
                )
    for flow in project.flows.values():
        for hook in ("on_start", "on_complete", "on_cancel", "on_error"):
            invocation = getattr(flow.lifecycle, hook)
            if invocation:
                yield from _invocation_usages(invocation, "flow", flow.id, f"lifecycle.{hook}", flow.source_path)
        for state in flow.states.values():
            entity = f"{flow.id}.{state.id}"
            if state.on_enter:
                yield from _invocation_usages(state.on_enter, "state", entity, "on_enter", flow.source_path)
            if state.on_message:
                yield from _invocation_usages(state.on_message, "state", entity, "on_message", flow.source_path)
            for event_id, invocation in state.events.items():
                yield from _invocation_usages(invocation, "state_event", f"{entity}.{event_id}", f"events.{event_id}", flow.source_path)
    for command in project.commands.commands:
        yield from _action_usages(command.action, "command", command.name, "action", "commands.json")
    for name, action in (
        ("message_fallback", project.commands.message_fallback),
        ("command_fallback", project.commands.command_fallback),
    ):
        if action:
            yield from _action_usages(action, "fallback", name, name, "commands.json")
    for schedule in project.schedules.values():
        yield HandlerUsage(schedule.handler, "schedule", schedule.id, "handler", schedule.source_path)


def _invocation_usages(
    invocation: HandlerInvocation,
    entity_type: str,
    entity_id: str,
    field: str,
    source: str | None,
) -> Iterator[HandlerUsage]:
    yield HandlerUsage(invocation.handler, entity_type, entity_id, f"{field}.handler", source)
    for outcome, action in invocation.outcomes.items():
        yield from _action_usages(action, entity_type, entity_id, f"{field}.outcomes.{outcome}", source)


def _action_usages(
    action: ActionSpec,
    entity_type: str,
    entity_id: str,
    field: str,
    source: str | None,
) -> Iterator[HandlerUsage]:
    if action.type == "handler.invoke" and action.handler:
        yield HandlerUsage(action.handler, entity_type, entity_id, f"{field}.handler", source)
    if action.type == "task.enqueue" and action.target:
        yield HandlerUsage(action.target, entity_type, entity_id, f"{field}.target", source)
    for outcome, nested in action.outcomes.items():
        yield from _action_usages(nested, entity_type, entity_id, f"{field}.outcomes.{outcome}", source)
