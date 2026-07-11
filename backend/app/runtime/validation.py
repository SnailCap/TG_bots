from __future__ import annotations

import re
from pathlib import Path

from app.domain.enums import NodeType, ValidationSeverity
from app.domain.flow import Flow, Node
from app.domain.ports.projects import ProjectRepository
from app.domain.project import BotProject
from app.domain.validation import ValidationIssue

from .actions import ProjectActionLoader
from .conditions import ConditionEvaluator
from .errors import ActionDiscoveryError

_VARIABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


class RuntimeProjectValidator:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        action_loader: ProjectActionLoader,
    ) -> None:
        self._projects = projects
        self._actions = action_loader
        self._condition_operators = set(ConditionEvaluator().supported_operators)

    def validate(
        self,
        project: BotProject,
        project_root: Path,
        *,
        token: str | None,
    ) -> tuple[ValidationIssue, ...]:
        issues: list[ValidationIssue] = []
        if not token:
            issues.append(self._issue("runtime.token_missing", "Telegram token is not configured"))
        start_flow_id = project.configuration.start_flow_id
        if not start_flow_id:
            issues.append(self._issue("runtime.start_flow_missing", "Start flow is not configured"))

        try:
            flows = tuple(self._projects.list_flows(project_root))
        except Exception as exc:
            return tuple(issues + [self._issue("flow.load_error", str(exc))])
        flows_by_id = {flow.id: flow for flow in flows}
        if start_flow_id and start_flow_id not in flows_by_id:
            issues.append(
                self._issue(
                    "runtime.start_flow_not_found",
                    f"Configured start flow '{start_flow_id}' does not exist",
                    entity_type="flow",
                    entity_id=start_flow_id,
                )
            )

        try:
            action_names = {
                action.name
                for action in self._actions.list_actions(project.id, project_root)
            }
        except ActionDiscoveryError as exc:
            action_names = set()
            issues.append(
                self._issue(
                    "script.discovery_error",
                    str(exc),
                    entity_type="script",
                )
            )

        for flow in flows:
            issues.extend(self._validate_flow(flow, action_names))
        return tuple(issues)

    def _validate_flow(
        self,
        flow: Flow,
        action_names: set[str],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        nodes = {node.id: node for node in flow.nodes}
        if len(nodes) != len(flow.nodes):
            issues.append(self._issue("flow.duplicate_node_id", "Flow contains duplicate node ids", flow))

        starts = [node for node in flow.nodes if node.type is NodeType.START]
        if len(starts) != 1:
            issues.append(
                self._issue(
                    "flow.start_count",
                    f"Flow must contain exactly one Start node; found {len(starts)}",
                    flow,
                )
            )
        if flow.start_node_id and flow.start_node_id not in nodes:
            issues.append(
                self._issue(
                    "flow.start_node_missing",
                    f"start_node_id '{flow.start_node_id}' does not exist",
                    flow,
                )
            )

        outgoing: dict[str, int] = {}
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in nodes}
        for transition in flow.transitions:
            outgoing[transition.source_node_id] = outgoing.get(transition.source_node_id, 0) + 1
            if transition.source_node_id not in nodes:
                issues.append(
                    self._issue(
                        "transition.source_missing",
                        f"Transition source '{transition.source_node_id}' does not exist",
                        entity_type="transition",
                        entity_id=transition.id,
                    )
                )
            if transition.target_node_id not in nodes:
                issues.append(
                    self._issue(
                        "transition.target_missing",
                        f"Transition target '{transition.target_node_id}' does not exist",
                        entity_type="transition",
                        entity_id=transition.id,
                    )
                )
            if transition.source_node_id in adjacency:
                adjacency[transition.source_node_id].add(transition.target_node_id)

        for node in flow.nodes:
            if node.type is not NodeType.END and outgoing.get(node.id, 0) == 0:
                issues.append(
                    self._issue(
                        "node.transition_missing",
                        "Node requires an outgoing transition",
                        entity_type="node",
                        entity_id=node.id,
                    )
                )
            issues.extend(self._validate_node(node, action_names))

        start_id = flow.start_node_id or (starts[0].id if len(starts) == 1 else None)
        if start_id in nodes:
            reachable: set[str] = set()
            stack = [start_id]
            while stack:
                current = stack.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                stack.extend(adjacency.get(current, ()))
            for node_id in nodes.keys() - reachable:
                issues.append(
                    self._issue(
                        "node.unreachable",
                        "Node is unreachable from Start",
                        entity_type="node",
                        entity_id=node_id,
                        severity=ValidationSeverity.WARNING,
                    )
                )
        return issues

    def _validate_node(
        self,
        node: Node,
        action_names: set[str],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        config = node.config
        if node.type in {NodeType.SEND_MESSAGE, NodeType.END}:
            raw_media = config.get("media")
            has_media = (
                isinstance(raw_media, dict)
                and any(raw_media.get(key) for key in ("source", "path", "url"))
            ) or any(
                config.get(key)
                for key in ("media_path", "photo", "image", "document", "file")
            )
            if (
                node.type is NodeType.SEND_MESSAGE
                and not config.get("text")
                and not has_media
            ):
                issues.append(self._node_issue(node, "node.message_missing", "Message node requires text or media"))
        elif node.type is NodeType.ASK_INPUT:
            variable = str(config.get("variable_name", config.get("variable", "")))
            if not _VARIABLE_NAME.fullmatch(variable):
                issues.append(self._node_issue(node, "node.variable_invalid", "Ask Input has an invalid variable name"))
            if not config.get("prompt", config.get("text")):
                issues.append(self._node_issue(node, "node.prompt_missing", "Ask Input requires a prompt"))
        elif node.type is NodeType.CHOICE:
            if not config.get("prompt", config.get("text")):
                issues.append(self._node_issue(node, "node.prompt_missing", "Choice requires a prompt"))
        elif node.type is NodeType.ACTION:
            name = str(config.get("action_name", config.get("action", "")))
            if not name:
                issues.append(self._node_issue(node, "node.action_missing", "Action node requires action_name"))
            elif name not in action_names:
                issues.append(self._node_issue(node, "node.action_not_found", f"Registered action '{name}' was not found"))
        elif node.type is NodeType.CONDITION:
            expression = config.get("condition", config)
            if isinstance(expression, dict) and not ("all" in expression or "any" in expression):
                operator = str(expression.get("operator", expression.get("op", "eq"))).casefold()
                if operator not in self._condition_operators:
                    issues.append(self._node_issue(node, "node.condition_operator_invalid", f"Unsupported condition operator '{operator}'"))
        return issues

    @staticmethod
    def _node_issue(node: Node, code: str, message: str) -> ValidationIssue:
        return RuntimeProjectValidator._issue(
            code,
            message,
            entity_type="node",
            entity_id=node.id,
        )

    @staticmethod
    def _issue(
        code: str,
        message: str,
        flow: Flow | None = None,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        severity: ValidationSeverity = ValidationSeverity.ERROR,
    ) -> ValidationIssue:
        if flow is not None:
            entity_type = entity_type or "flow"
            entity_id = entity_id or flow.id
        return ValidationIssue(
            severity=severity,
            code=code,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id,
        )
