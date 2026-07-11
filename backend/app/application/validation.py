from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.domain.enums import NodeType, TransitionKind, ValidationSeverity, VariableType
from app.domain.flow import Flow, Node, Transition
from app.domain.project import BotProject
from app.domain.ports.projects import ProjectRepository
from app.domain.validation import ValidationIssue
from app.infrastructure.scripts import ScriptDiscoveryResult
from app.infrastructure.scripts import ScriptDiscovery

from .projects import ProjectApplicationService

_VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)


class FlowValidator:
    def validate(
        self,
        flow: Flow,
        *,
        action_names: Iterable[str] = (),
    ) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        known_actions = set(action_names)
        if flow.schema_version != 1:
            issues.append(self._issue("flow.schema_version", "Unsupported flow schema version", flow))

        nodes_by_id: dict[str, Node] = {}
        for node in flow.nodes:
            if node.id in nodes_by_id:
                issues.append(
                    self._issue(
                        "node.duplicate_id",
                        f"Duplicate node id: {node.id}",
                        flow,
                        node=node,
                    )
                )
            nodes_by_id[node.id] = node

        starts = [node for node in flow.nodes if node.type == NodeType.START]
        if len(starts) != 1:
            issues.append(
                self._issue(
                    "flow.start_count",
                    "A flow must contain exactly one Start node",
                    flow,
                    hint="Add one Start node and remove duplicates",
                )
            )
        if flow.start_node_id is None:
            issues.append(self._issue("flow.start_missing", "start_node_id is not configured", flow))
        elif flow.start_node_id not in nodes_by_id:
            issues.append(
                self._issue(
                    "flow.start_broken",
                    "start_node_id references a missing node",
                    flow,
                )
            )
        elif nodes_by_id[flow.start_node_id].type != NodeType.START:
            issues.append(
                self._issue(
                    "flow.start_wrong_type",
                    "start_node_id must reference a Start node",
                    flow,
                    node=nodes_by_id[flow.start_node_id],
                )
            )

        outgoing: dict[str, list[str]] = {node.id: [] for node in flow.nodes}
        outgoing_edges: dict[str, list[Transition]] = {node.id: [] for node in flow.nodes}
        transition_ids: set[str] = set()
        branch_keys: set[tuple[str, str]] = set()
        for transition in flow.transitions:
            if transition.id in transition_ids:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        code="transition.duplicate_id",
                        message=f"Duplicate transition id: {transition.id}",
                        entity_type="transition",
                        entity_id=transition.id,
                        path=f"flows/{flow.id}.flow.json",
                    )
                )
            transition_ids.add(transition.id)
            if transition.source_node_id not in nodes_by_id:
                issues.append(
                    self._transition_issue(
                        "transition.source_missing",
                        "Transition source node does not exist",
                        flow,
                        transition.id,
                    )
                )
            else:
                outgoing[transition.source_node_id].append(transition.target_node_id)
                outgoing_edges[transition.source_node_id].append(transition)
            if transition.target_node_id not in nodes_by_id:
                issues.append(
                    self._transition_issue(
                        "transition.target_missing",
                        "Transition target node does not exist",
                        flow,
                        transition.id,
                    )
                )
            branch = transition.outcome or transition.label
            if branch:
                key = (transition.source_node_id, branch)
                if key in branch_keys:
                    issues.append(
                        self._transition_issue(
                            "transition.duplicate_branch",
                            f"Duplicate outgoing branch: {branch}",
                            flow,
                            transition.id,
                        )
                    )
                branch_keys.add(key)

        for node in flow.nodes:
            node_outgoing = outgoing.get(node.id, [])
            if node.type == NodeType.END and node_outgoing:
                issues.append(
                    self._issue(
                        "node.end_has_transition",
                        "End nodes cannot have outgoing transitions",
                        flow,
                        node=node,
                    )
                )
            elif node.type != NodeType.END and not node_outgoing:
                issues.append(
                    self._issue(
                        "node.transition_missing",
                        "Node requires at least one outgoing transition",
                        flow,
                        node=node,
                    )
                )
            issues.extend(
                self._validate_node(
                    flow,
                    node,
                    known_actions,
                    outgoing_edges.get(node.id, []),
                )
            )

        if flow.start_node_id in nodes_by_id:
            reachable = self._reachable(flow.start_node_id, outgoing)
            for node in flow.nodes:
                if node.id not in reachable:
                    issues.append(
                        self._issue(
                            "node.unreachable",
                            "Node is unreachable from Start",
                            flow,
                            node=node,
                            severity=ValidationSeverity.WARNING,
                        )
                    )
        return tuple(issues)

    def _validate_node(
        self,
        flow: Flow,
        node: Node,
        action_names: set[str],
        outgoing: list[Transition],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if node.type == NodeType.SEND_MESSAGE:
            has_text = self._nonempty(node.config.get("text"))
            raw_media = node.config.get("media")
            has_media = (
                isinstance(raw_media, dict)
                and any(
                    self._nonempty(raw_media.get(key))
                    for key in ("source", "path", "url")
                )
            ) or any(
                self._nonempty(node.config.get(key))
                for key in (
                    "media_path",
                    "photo",
                    "image",
                    "document",
                    "file",
                )
            )
            if not has_text and not has_media:
                issues.append(
                    self._issue(
                        "send_message.content_missing",
                        "Send Message requires text or a media/file reference",
                        flow,
                        node=node,
                    )
                )
        elif node.type == NodeType.ASK_INPUT:
            if not self._nonempty(node.config.get("text", node.config.get("prompt"))):
                issues.append(self._required(flow, node, "text"))
            variable = node.config.get("variable_name", node.config.get("variable"))
            if not isinstance(variable, str) or not _VARIABLE_NAME.fullmatch(variable):
                issues.append(
                    self._issue(
                        "ask_input.invalid_variable",
                        "Ask Input requires a valid variable name",
                        flow,
                        node=node,
                        hint="Use names such as user.name or request_id",
                    )
                )
            expected = node.config.get(
                "expected_type",
                node.config.get("input_type", VariableType.STRING.value),
            )
            try:
                VariableType(expected)
            except (TypeError, ValueError):
                issues.append(
                    self._issue(
                        "ask_input.invalid_type",
                        f"Unsupported input type: {expected}",
                        flow,
                        node=node,
                    )
                )
            attempts = node.config.get("max_attempts", 3)
            if not isinstance(attempts, int) or attempts < 1:
                issues.append(
                    self._issue(
                        "ask_input.invalid_attempts",
                        "max_attempts must be a positive integer",
                        flow,
                        node=node,
                    )
                )
        elif node.type == NodeType.CHOICE and len(outgoing) < 2:
            issues.append(
                self._issue(
                    "choice.branches_missing",
                    "Choice requires at least two outgoing branches",
                    flow,
                    node=node,
                )
            )
        elif node.type == NodeType.ACTION:
            action_name = node.config.get("action_name", node.config.get("action"))
            if not self._nonempty(action_name):
                issues.append(self._required(flow, node, "action_name"))
            elif str(action_name) not in action_names:
                issues.append(
                    self._issue(
                        "action.reference_missing",
                        f"Registered action not found: {action_name}",
                        flow,
                        node=node,
                        hint="Create the action or select another registered action",
                    )
                )
        elif node.type == NodeType.CONDITION:
            if not self._valid_condition(node.config):
                issues.append(
                    self._issue(
                        "condition.logic_missing",
                        "Condition requires an allowlisted variable/operator/value mapping, all, or any",
                        flow,
                        node=node,
                    )
                )
            if len(outgoing) < 2:
                issues.append(
                    self._issue(
                        "condition.branches_missing",
                        "Condition requires at least two outgoing branches",
                        flow,
                        node=node,
                    )
                )
        issues.extend(self._validate_edge_contract(flow, node, outgoing))
        return issues

    def _validate_edge_contract(
        self,
        flow: Flow,
        node: Node,
        outgoing: list[Transition],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        kinds = {edge.kind for edge in outgoing}
        if node.type == NodeType.START:
            if len(outgoing) != 1 or kinds != {TransitionKind.AUTOMATIC}:
                issues.append(
                    self._issue(
                        "start.invalid_transition",
                        "Start requires exactly one automatic transition",
                        flow,
                        node=node,
                    )
                )
        elif node.type == NodeType.SEND_MESSAGE:
            allowed = {
                TransitionKind.AUTOMATIC,
                TransitionKind.SUCCESS,
                TransitionKind.BUTTON,
            }
            issues.extend(self._unsupported_edges(flow, node, outgoing, allowed))
        elif node.type == NodeType.ASK_INPUT:
            allowed = {
                TransitionKind.INPUT,
                TransitionKind.SUCCESS,
                TransitionKind.AUTOMATIC,
                TransitionKind.ERROR,
            }
            issues.extend(self._unsupported_edges(flow, node, outgoing, allowed))
            if not kinds.intersection(
                {TransitionKind.INPUT, TransitionKind.SUCCESS, TransitionKind.AUTOMATIC}
            ):
                issues.append(
                    self._issue(
                        "ask_input.success_transition_missing",
                        "Ask Input requires an input, success, or automatic transition",
                        flow,
                        node=node,
                    )
                )
            if TransitionKind.ERROR not in kinds:
                issues.append(
                    self._issue(
                        "ask_input.error_transition_missing",
                        "Ask Input requires an error transition for exhausted attempts",
                        flow,
                        node=node,
                    )
                )
        elif node.type == NodeType.CHOICE:
            allowed = {TransitionKind.BUTTON, TransitionKind.INPUT}
            issues.extend(self._unsupported_edges(flow, node, outgoing, allowed))
            for edge in outgoing:
                if not self._nonempty(edge.outcome) and not self._nonempty(edge.label):
                    issues.append(
                        self._transition_issue(
                            "choice.selector_missing",
                            "Choice transition requires an outcome or label selector",
                            flow,
                            edge.id,
                        )
                    )
        elif node.type == NodeType.CONDITION:
            issues.extend(
                self._unsupported_edges(
                    flow,
                    node,
                    outgoing,
                    {TransitionKind.CONDITION},
                )
            )
            outcomes = {str(edge.outcome).casefold() for edge in outgoing if edge.outcome}
            if not {"true", "false"}.issubset(outcomes):
                issues.append(
                    self._issue(
                        "condition.outcomes_missing",
                        "Condition requires condition transitions with true and false outcomes",
                        flow,
                        node=node,
                    )
                )
        elif node.type == NodeType.ACTION:
            allowed = {
                TransitionKind.SUCCESS,
                TransitionKind.ACTION,
                TransitionKind.AUTOMATIC,
                TransitionKind.ERROR,
            }
            issues.extend(self._unsupported_edges(flow, node, outgoing, allowed))
            if not kinds.intersection(
                {TransitionKind.SUCCESS, TransitionKind.ACTION, TransitionKind.AUTOMATIC}
            ):
                issues.append(
                    self._issue(
                        "action.success_transition_missing",
                        "Action requires a success, action, or automatic transition",
                        flow,
                        node=node,
                    )
                )
            if TransitionKind.ERROR not in kinds:
                issues.append(
                    self._issue(
                        "action.error_transition_missing",
                        "Action requires an error transition",
                        flow,
                        node=node,
                    )
                )
        return issues

    def _unsupported_edges(
        self,
        flow: Flow,
        node: Node,
        outgoing: list[Transition],
        allowed: set[TransitionKind],
    ) -> list[ValidationIssue]:
        return [
            self._transition_issue(
                "transition.kind_not_supported",
                f"{node.type.value} does not support {edge.kind.value} transitions",
                flow,
                edge.id,
            )
            for edge in outgoing
            if edge.kind not in allowed
        ]

    @classmethod
    def _valid_condition(cls, value: object) -> bool:
        if not isinstance(value, dict):
            return False
        if "all" in value or "any" in value:
            key = "all" if "all" in value else "any"
            children = value.get(key)
            return (
                isinstance(children, list)
                and bool(children)
                and all(cls._valid_condition(child) for child in children)
            )
        variable = value.get("variable")
        operator = value.get("operator")
        allowed_operators = {
            "eq",
            "ne",
            "gt",
            "gte",
            "lt",
            "lte",
            "contains",
            "not_contains",
            "in",
            "not_in",
            "truthy",
            "falsy",
            "exists",
            "not_exists",
        }
        return isinstance(variable, str) and bool(variable.strip()) and operator in allowed_operators

    @staticmethod
    def _reachable(start: str, outgoing: dict[str, list[str]]) -> set[str]:
        seen: set[str] = set()
        pending = [start]
        while pending:
            node_id = pending.pop()
            if node_id in seen:
                continue
            seen.add(node_id)
            pending.extend(target for target in outgoing.get(node_id, []) if target not in seen)
        return seen

    def _required(self, flow: Flow, node: Node, field: str) -> ValidationIssue:
        return self._issue(
            "node.required_field",
            f"Required field is missing: {field}",
            flow,
            node=node,
        )

    @staticmethod
    def _nonempty(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _issue(
        code: str,
        message: str,
        flow: Flow,
        *,
        node: Node | None = None,
        hint: str | None = None,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
    ) -> ValidationIssue:
        return ValidationIssue(
            severity=severity,
            code=code,
            message=message,
            entity_type="node" if node is not None else "flow",
            entity_id=node.id if node is not None else flow.id,
            path=f"flows/{flow.id}.flow.json",
            hint=hint,
        )

    @staticmethod
    def _transition_issue(
        code: str,
        message: str,
        flow: Flow,
        transition_id: str,
    ) -> ValidationIssue:
        return ValidationIssue(
            severity=ValidationSeverity.ERROR,
            code=code,
            message=message,
            entity_type="transition",
            entity_id=transition_id,
            path=f"flows/{flow.id}.flow.json",
        )


class ProjectValidator:
    def __init__(self, flow_validator: FlowValidator) -> None:
        self._flows = flow_validator

    def validate(
        self,
        project: BotProject,
        flows: Iterable[Flow],
        scripts: ScriptDiscoveryResult,
    ) -> ValidationReport:
        issues = list(scripts.issues)
        flow_values = tuple(flows)
        flow_ids = {flow.id for flow in flow_values}
        action_names = {action.name for action in scripts.actions}
        if project.configuration.secret_ref is None:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="project.token_missing",
                    message="Telegram token is not configured",
                    entity_type="project",
                    entity_id=project.id,
                    hint="Validate and save a Telegram bot token in Settings",
                )
            )
        if not flow_values:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="project.flows_missing",
                    message="Project has no flows",
                    entity_type="project",
                    entity_id=project.id,
                )
            )
        start_flow = project.configuration.start_flow_id
        if start_flow is None:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="project.start_flow_missing",
                    message="Start flow is not configured",
                    entity_type="project",
                    entity_id=project.id,
                )
            )
        elif start_flow not in flow_ids:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    code="project.start_flow_broken",
                    message="Configured start flow does not exist",
                    entity_type="project",
                    entity_id=project.id,
                )
            )
        for flow in flow_values:
            issues.extend(self._flows.validate(flow, action_names=action_names))
        return ValidationReport(tuple(issues))


class ValidationApplicationService:
    def __init__(
        self,
        projects: ProjectApplicationService,
        repository: ProjectRepository,
        script_discovery: ScriptDiscovery,
        validator: ProjectValidator,
    ) -> None:
        self._projects = projects
        self._repository = repository
        self._script_discovery = script_discovery
        self._validator = validator

    def validate(
        self,
        project_id: str,
        *,
        validate_imports: bool = True,
    ) -> ValidationReport:
        opened = self._projects.get(project_id)
        flows = self._repository.list_flows(opened.path)
        scripts = self._script_discovery.discover(
            opened.path,
            validate_imports=validate_imports,
        )
        return self._validator.validate(opened.project, flows, scripts)
