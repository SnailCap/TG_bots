from __future__ import annotations

import keyword
import re
from collections import Counter, deque
from pathlib import Path, PurePosixPath
from typing import Iterable

from jinja2 import Environment, TemplateError

from ..content import (
    CodeBlock,
    CustomEmojiNode,
    LegacyTemplateBlock,
    TextNode,
    VariableNode,
    validate_content_document,
)

from .inspection import inspect_handler_source
from .models import (
    ACTION_TYPES,
    HANDLER_KINDS,
    ActionSpec,
    Diagnostic,
    HandlerInvocation,
    ProjectDefinition,
)

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_COMMAND = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
class ProjectValidationError(RuntimeError):
    def __init__(self, diagnostics: Iterable[Diagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        summary = "; ".join(item.message for item in self.diagnostics if item.level == "error")
        super().__init__(summary or "Project validation failed.")


def load_and_validate_project(
    root: str | Path,
    *,
    inspect_code: bool = False,
) -> tuple[ProjectDefinition | None, list[Diagnostic]]:
    """Load a project and normalize parse failures into the shared diagnostic contract."""

    from .loader import ProjectLoadError, ProjectLoader

    try:
        project = ProjectLoader().load(root)
    except ProjectLoadError as error:
        return None, [Diagnostic("error", "project_load", str(error))]
    return project, validate_project(project, inspect_code=inspect_code)


def validate_project(project: ProjectDefinition, *, inspect_code: bool = False) -> list[Diagnostic]:
    """Validate the complete application graph with stable, Studio-friendly diagnostics."""

    diagnostics: list[Diagnostic] = []
    used_handlers: set[str] = set()
    known_event_ids = frozenset(
        event_id
        for flow in project.flows.values()
        for state in flow.states.values()
        for event_id in state.events
    )

    def issue(
        level: str,
        code: str,
        message: str,
        *,
        source: str | None = None,
        entity: str | None = None,
        field: str | None = None,
    ) -> None:
        diagnostics.append(Diagnostic(level, code, message, source, entity, field))

    def valid_id(value: str, source: str | None, entity: str) -> None:
        if not _ID.fullmatch(value):
            issue("error", "invalid_id", f"Invalid id '{value}'.", source=source, entity=entity, field="id")

    def validate_handler_reference(
        handler_id: str,
        expected_kind: str,
        source: str | None,
        entity: str,
        field: str,
    ) -> None:
        binding = project.handlers.get(handler_id)
        if binding is None:
            issue("error", "handler_binding_missing", f"Unknown handler '{handler_id}'.", source=source, entity=entity, field=field)
            return
        used_handlers.add(handler_id)
        if binding.kind != expected_kind:
            issue(
                "error",
                "handler_kind_mismatch",
                f"Handler '{handler_id}' has kind '{binding.kind}', expected '{expected_kind}'.",
                source=source,
                entity=entity,
                field=field,
            )

    def validate_outcomes(
        handler_id: str,
        outcomes: dict | object,
        expected_kind: str,
        source: str | None,
        entity: str,
        field: str,
        current_flow: str | None,
    ) -> None:
        outcome_map = outcomes if isinstance(outcomes, dict) else dict(outcomes)  # type: ignore[arg-type]
        binding = project.handlers.get(handler_id)
        if binding:
            if "success" not in outcome_map:
                issue("error", "outcome_route_missing", f"Handler '{handler_id}' has no explicit success route.", source=source, entity=entity, field=field)
            for name in binding.outcomes:
                if name not in outcome_map:
                    issue("error", "outcome_route_missing", f"Handler '{handler_id}' declares outcome '{name}' without a route.", source=source, entity=entity, field=field)
            unknown = set(outcome_map) - {"success", *binding.outcomes}
            for name in sorted(unknown):
                issue("error", "unknown_outcome", f"Outcome route '{name}' is not declared by handler '{handler_id}'.", source=source, entity=entity, field=f"{field}.{name}")
        for name, route in outcome_map.items():
            validate_action(route, expected_kind, source, entity, f"{field}.{name}", current_flow)

    def validate_invocation(
        invocation: HandlerInvocation,
        expected_kind: str,
        source: str | None,
        entity: str,
        field: str,
        current_flow: str | None = None,
    ) -> None:
        validate_handler_reference(invocation.handler, expected_kind, source, entity, f"{field}.handler")
        validate_outcomes(invocation.handler, invocation.outcomes, expected_kind, source, entity, f"{field}.outcomes", current_flow)

    def validate_action(
        action: ActionSpec,
        expected_kind: str,
        source: str | None,
        entity: str,
        field: str,
        current_flow: str | None = None,
    ) -> None:
        if action.type not in ACTION_TYPES:
            issue("error", "invalid_action_type", f"Unknown action type '{action.type}'.", source=source, entity=entity, field=f"{field}.type")
            return
        if action.type == "view.render":
            if not action.target or action.target not in project.views:
                issue("error", "unknown_view_reference", f"Action references unknown view '{action.target}'.", source=source, entity=entity, field=f"{field}.target")
        elif action.type == "flow.start":
            if not action.target or action.target not in project.flows:
                issue("error", "unknown_flow_reference", f"Action references unknown flow '{action.target}'.", source=source, entity=entity, field=f"{field}.target")
        elif action.type == "flow.goto":
            flow = project.flows.get(current_flow or "")
            if not action.target or flow is None or action.target not in flow.states:
                issue("error", "unknown_state_reference", f"Action references unknown state '{action.target}' in flow '{current_flow}'.", source=source, entity=entity, field=f"{field}.target")
        elif action.type == "flow.event":
            if not action.target:
                issue("error", "action_target_missing", "flow.event requires a named event target.", source=source, entity=entity, field=f"{field}.target")
            elif action.target not in known_event_ids:
                issue(
                    "error",
                    "unknown_event_reference",
                    f"Action references unknown flow event '{action.target}'.",
                    source=source,
                    entity=entity,
                    field=f"{field}.target",
                )
            if expected_kind != "button":
                issue("error", "action_context_invalid", "flow.event can only be emitted by a button callback.", source=source, entity=entity, field=field)
        elif action.type == "handler.invoke":
            if not action.handler:
                issue("error", "handler_binding_missing", "handler.invoke requires a handler.", source=source, entity=entity, field=f"{field}.handler")
            else:
                validate_handler_reference(action.handler, expected_kind, source, entity, f"{field}.handler")
                validate_outcomes(action.handler, action.outcomes, expected_kind, source, entity, f"{field}.outcomes", current_flow)
        elif action.type == "task.enqueue":
            if not action.target:
                issue("error", "handler_binding_missing", "task.enqueue requires a task handler target.", source=source, entity=entity, field=f"{field}.target")
            else:
                validate_handler_reference(action.target, "task", source, entity, f"{field}.target")
            if action.delay_seconds < 0:
                issue("error", "invalid_action_delay", "task.enqueue delay_seconds cannot be negative.", source=source, entity=entity, field=f"{field}.delay_seconds")
        if action.view and action.view not in project.views:
            issue("error", "unknown_view_reference", f"Action references unknown view '{action.view}'.", source=source, entity=entity, field=f"{field}.view")

    valid_id(project.manifest.id, "bot.json", project.manifest.id)
    if not _MODULE.fullmatch(project.manifest.package) or any(keyword.iskeyword(part) for part in project.manifest.package.split(".")):
        issue("error", "invalid_package", f"Invalid Python package '{project.manifest.package}'.", source="bot.json", entity=project.manifest.id, field="package")
    if project.manifest.entry_view not in project.views:
        issue("error", "missing_entry_view", f"Entry view '{project.manifest.entry_view}' does not exist.", source="bot.json", field="entry_view")
    if project.manifest.start.flow not in project.flows:
        issue("error", "missing_start_flow", f"Start flow '{project.manifest.start.flow}' does not exist.", source="bot.json", field="start.flow")

    action_ids = [button.id for view in project.views.values() for row in view.keyboard for button in row]
    for action_id, count in Counter(action_ids).items():
        if count > 1:
            issue("error", "duplicate_action_id", f"Button action id '{action_id}' is used {count} times.", entity=action_id)

    document_ids = Counter(document.id for document in project.content_documents.values())
    for document_id, count in document_ids.items():
        if count > 1:
            issue(
                "error",
                "duplicate_content_document_id",
                f"Content document id '{document_id}' is used {count} times.",
                entity=document_id,
            )
    for document_name, document in project.content_documents.items():
        source_path = f"content/{document_name}"
        valid_id(document.id, source_path, document.id)
        for diagnostic in validate_content_document(document):
            issue(
                diagnostic.severity,
                diagnostic.code,
                diagnostic.message,
                source=source_path,
                entity=document.id,
                field=diagnostic.path,
            )
        for block_index, block in enumerate(document.content):
            if not isinstance(block, LegacyTemplateBlock):
                continue
            try:
                Environment().parse(block.source)
            except TemplateError as error:
                issue(
                    "error",
                    "jinja_syntax",
                    f"Invalid legacy Jinja template: {error}",
                    source=source_path,
                    entity=document.id,
                    field=f"content[{block_index}].source",
                )

    for template_name, template_source in project.templates.items():
        template_path = f"templates/{template_name}"
        if not template_source.strip():
            issue(
                "error",
                "template_empty",
                f"Template '{template_name}' cannot render a Telegram message by itself.",
                source=template_path,
                entity=template_name,
                field="content",
            )
        try:
            Environment().parse(template_source)
        except TemplateError as error:
            issue(
                "error",
                "jinja_syntax",
                f"Invalid Jinja template: {error}",
                source=template_path,
                entity=template_name,
                field="content",
            )

    for view in project.views.values():
        valid_id(view.id, view.source_path, view.id)
        if view.text.document is not None:
            document_path = PurePosixPath(view.text.document)
            if (
                not view.text.document
                or view.text.document.strip() != view.text.document
                or "\\" in view.text.document
                or document_path.is_absolute()
                or ".." in document_path.parts
                or document_path.as_posix() != view.text.document
                or document_path.suffix.lower() != ".json"
            ):
                issue(
                    "error",
                    "content_document_path_invalid",
                    f"View '{view.id}' has an invalid content document path.",
                    source=view.source_path,
                    entity=view.id,
                    field="text.document",
                )
            elif view.text.document not in project.content_documents:
                issue(
                    "error",
                    "content_document_missing",
                    f"View '{view.id}' references missing content document '{view.text.document}'.",
                    source=view.source_path,
                    entity=view.id,
                    field="text.document",
                )
            elif not _content_document_has_potential_output(
                project.content_documents[view.text.document]
            ):
                issue(
                    "error",
                    "content_document_empty",
                    f"View '{view.id}' references a content document with no renderable text.",
                    source=view.source_path,
                    entity=view.id,
                    field="text.document",
                )
        source_text = view.text.inline
        if view.text.template:
            if view.text.template not in project.templates:
                issue("error", "template_missing", f"View '{view.id}' references missing template '{view.text.template}'.", source=view.source_path, entity=view.id, field="text.template")
        if source_text is not None:
            if not source_text.strip():
                issue(
                    "error",
                    "view_text_empty",
                    f"View '{view.id}' inline text cannot be empty.",
                    source=view.source_path,
                    entity=view.id,
                    field="text.inline",
                )
            try:
                Environment().parse(source_text)
            except TemplateError as error:
                issue("error", "jinja_syntax", f"Invalid Jinja template: {error}", source=view.source_path, entity=view.id, field="text")
        for row_index, row in enumerate(view.keyboard):
            for button_index, button in enumerate(row):
                valid_id(button.id, view.source_path, button.id)
                if len(f"v3:a:{button.id}".encode("utf-8")) > 64:
                    issue("error", "callback_encoding_invalid", f"Button id '{button.id}' exceeds Telegram's callback limit.", source=view.source_path, entity=button.id, field="id")
                validate_action(button.action, "button", view.source_path, button.id, f"keyboard.{row_index}.{button_index}.action")

    for flow in project.flows.values():
        valid_id(flow.id, flow.source_path, flow.id)
        if flow.initial_state not in flow.states:
            issue("error", "missing_initial_state", f"Flow '{flow.id}' initial state '{flow.initial_state}' does not exist.", source=flow.source_path, entity=flow.id, field="initial_state")
        for hook_name in ("on_start", "on_complete", "on_cancel", "on_error"):
            invocation = getattr(flow.lifecycle, hook_name)
            if invocation:
                route_flow = flow.id if hook_name == "on_start" else None
                validate_invocation(invocation, "lifecycle", flow.source_path, flow.id, f"lifecycle.{hook_name}", route_flow)
        for state in flow.states.values():
            valid_id(state.id, flow.source_path, state.id)
            if state.view not in project.views:
                issue("error", "missing_state_view", f"State '{flow.id}.{state.id}' references unknown view '{state.view}'.", source=flow.source_path, entity=f"{flow.id}.{state.id}", field="view")
            if state.on_enter:
                validate_invocation(state.on_enter, "lifecycle", flow.source_path, f"{flow.id}.{state.id}", "on_enter", flow.id)
            if state.on_message:
                validate_invocation(state.on_message, "message", flow.source_path, f"{flow.id}.{state.id}", "on_message", flow.id)
            for event_id, invocation in state.events.items():
                valid_id(event_id, flow.source_path, event_id)
                validate_invocation(invocation, "button", flow.source_path, f"{flow.id}.{state.id}", f"events.{event_id}", flow.id)
        _validate_reachability(flow, issue)

    command_names = [command.name.lower() for command in project.commands.commands]
    for name, count in Counter(command_names).items():
        if count > 1:
            issue("error", "command_collision", f"Command '/{name}' is declared more than once.", source="commands.json", entity=name)
    for command in project.commands.commands:
        if not _COMMAND.fullmatch(command.name):
            issue("error", "invalid_command", f"Invalid command '/{command.name}'.", source="commands.json", entity=command.name, field="name")
        if command.name == "start":
            issue("error", "command_collision", "Command '/start' is reserved by project start behavior.", source="commands.json", entity=command.name)
        validate_action(command.action, "command", "commands.json", command.name, "action")
    if project.commands.message_fallback:
        validate_action(project.commands.message_fallback, "message", "commands.json", "message_fallback", "message_fallback")
    if project.commands.command_fallback:
        validate_action(project.commands.command_fallback, "command", "commands.json", "command_fallback", "command_fallback")

    for schedule in project.schedules.values():
        valid_id(schedule.id, schedule.source_path, schedule.id)
        if schedule.trigger.type != "interval":
            issue("error", "unsupported_schedule_trigger", f"Schedule '{schedule.id}' trigger '{schedule.trigger.type}' is not supported yet.", source=schedule.source_path, entity=schedule.id, field="trigger.type")
        if schedule.trigger.seconds is None or schedule.trigger.seconds <= 0:
            issue("error", "invalid_schedule_trigger", f"Schedule '{schedule.id}' interval must be positive.", source=schedule.source_path, entity=schedule.id, field="trigger.seconds")
        validate_handler_reference(schedule.handler, "task", schedule.source_path, schedule.id, "handler")

    for binding in project.handlers.values():
        valid_id(binding.id, binding.source_path, binding.id)
        if (
            not _MODULE.fullmatch(binding.module)
            or any(keyword.iskeyword(part) for part in binding.module.split("."))
            or not binding.module.startswith(f"{project.manifest.package}.")
        ):
            issue("error", "invalid_handler_module", f"Handler '{binding.id}' module must be inside package '{project.manifest.package}'.", source=binding.source_path, entity=binding.id, field="module")
        if binding.kind not in HANDLER_KINDS:
            issue("error", "invalid_handler_kind", f"Handler '{binding.id}' has unknown kind '{binding.kind}'.", source=binding.source_path, entity=binding.id, field="kind")
        if len(set(binding.outcomes)) != len(binding.outcomes):
            issue("error", "duplicate_handler_outcome", f"Handler '{binding.id}' declares duplicate outcomes.", source=binding.source_path, entity=binding.id, field="outcomes")
        for outcome in binding.outcomes:
            if outcome == "success" or not _ID.fullmatch(outcome):
                issue("error", "invalid_handler_outcome", f"Handler '{binding.id}' has invalid outcome '{outcome}'.", source=binding.source_path, entity=binding.id, field="outcomes")
        if binding.kind == "task" and binding.outcomes:
            issue("error", "task_outcome_unsupported", f"Task handler '{binding.id}' cannot declare routed outcomes.", source=binding.source_path, entity=binding.id, field="outcomes")
        if binding.id not in used_handlers:
            issue("warning", "unused_handler", f"Handler '{binding.id}' is not referenced by the project graph.", source=binding.source_path, entity=binding.id)
        if inspect_code:
            inspection = inspect_handler_source(
                project.root,
                project.manifest.package,
                binding,
            )
            diagnostic = inspection.diagnostic(binding)
            if diagnostic is not None:
                diagnostics.append(diagnostic)

    return diagnostics


def _validate_reachability(flow, issue) -> None:
    if flow.initial_state not in flow.states:
        return
    edges: dict[str, set[str]] = {state_id: set() for state_id in flow.states}

    def collect(action: ActionSpec, current: str) -> None:
        if action.type == "flow.goto" and action.target:
            edges[current].add(action.target)
        for nested in action.outcomes.values():
            collect(nested, current)

    for state in flow.states.values():
        for invocation in (state.on_enter, state.on_message, *state.events.values()):
            if invocation:
                for action in invocation.outcomes.values():
                    collect(action, state.id)
    seen = {flow.initial_state}
    pending = deque([flow.initial_state])
    while pending:
        current = pending.popleft()
        for target in edges.get(current, ()):
            if target in flow.states and target not in seen:
                seen.add(target)
                pending.append(target)
    for state_id in flow.states.keys() - seen:
        issue("warning", "unreachable_state", f"State '{flow.id}.{state_id}' is unreachable from '{flow.initial_state}'.", source=flow.source_path, entity=f"{flow.id}.{state_id}")


def _content_document_has_potential_output(document) -> bool:
    for block in document.content:
        if isinstance(block, CodeBlock) and block.text.strip():
            return True
        if isinstance(block, LegacyTemplateBlock) and block.source.strip():
            return True
        content = getattr(block, "content", ())
        for node in content:
            if isinstance(node, TextNode) and node.text.strip():
                return True
            if isinstance(node, (VariableNode, CustomEmojiNode)):
                return True
    return False
