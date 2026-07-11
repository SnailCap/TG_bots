from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from app.domain.enums import NodeType, TransitionKind
from app.domain.flow import Flow, Node, NodePosition, Transition
from app.domain.project import BotConfiguration, BotIdentity, BotProject
from app.errors import ProjectFormatError, UnsupportedSchemaVersionError
from app.infrastructure.json_codec import dumps_json, loads_json

SCHEMA_VERSION = 1


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise ProjectFormatError(f"Field {field!r} must be an ISO datetime")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectFormatError(f"Invalid datetime in field {field!r}") from exc


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProjectFormatError(f"Field {field!r} must be an object")
    return value


def _string(value: Any, *, field: str, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProjectFormatError(f"Field {field!r} must be a non-empty string")
    return value.strip()


def _schema_version(data: Mapping[str, Any]) -> int:
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"Unsupported schema version: {version!r}",
            details={"supported": [SCHEMA_VERSION], "received": version},
        )
    return SCHEMA_VERSION


def project_to_dict(project: BotProject) -> dict[str, Any]:
    identity = project.configuration.identity
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": project.id,
            "name": project.name,
            "created_at": _iso(project.created_at),
            "updated_at": _iso(project.updated_at),
        },
        "bot": {
            "secret_ref": project.configuration.secret_ref,
            "start_flow_id": project.configuration.start_flow_id,
            "start_behavior": project.configuration.start_behavior,
            "identity": (
                {
                    "bot_id": identity.bot_id,
                    "username": identity.username,
                    "display_name": identity.display_name,
                }
                if identity is not None
                else None
            ),
            "metadata": dict(project.configuration.metadata),
        },
    }


def project_from_dict(raw: Mapping[str, Any]) -> BotProject:
    _schema_version(raw)
    project_data = _mapping(raw.get("project"), field="project")
    bot_data = _mapping(raw.get("bot", {}), field="bot")
    identity_data = bot_data.get("identity")
    identity: BotIdentity | None = None
    if identity_data is not None:
        identity_map = _mapping(identity_data, field="bot.identity")
        bot_id = identity_map.get("bot_id")
        if not isinstance(bot_id, int):
            raise ProjectFormatError("Field 'bot.identity.bot_id' must be an integer")
        identity = BotIdentity(
            bot_id=bot_id,
            username=_string(identity_map.get("username"), field="bot.identity.username") or "",
            display_name=_string(
                identity_map.get("display_name"), field="bot.identity.display_name"
            )
            or "",
        )
    metadata = bot_data.get("metadata", {})
    metadata_map = _mapping(metadata, field="bot.metadata")
    return BotProject(
        id=_string(project_data.get("id"), field="project.id") or "",
        name=_string(project_data.get("name"), field="project.name") or "",
        configuration=BotConfiguration(
            secret_ref=_string(
                bot_data.get("secret_ref"), field="bot.secret_ref", optional=True
            ),
            start_flow_id=_string(
                bot_data.get("start_flow_id"), field="bot.start_flow_id", optional=True
            ),
            identity=identity,
            start_behavior=str(bot_data.get("start_behavior") or "reset"),
            metadata=dict(metadata_map),
        ),
        schema_version=SCHEMA_VERSION,
        created_at=_datetime(project_data.get("created_at"), field="project.created_at"),
        updated_at=_datetime(project_data.get("updated_at"), field="project.updated_at"),
    )


def flow_to_dict(flow: Flow) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": flow.id,
        "name": flow.name,
        "start_node_id": flow.start_node_id,
        "nodes": [
            {
                "id": node.id,
                "type": node.type.value,
                "name": node.name,
                "position": {"x": node.position.x, "y": node.position.y},
                "config": dict(node.config),
            }
            for node in flow.nodes
        ],
        "transitions": [
            {
                "id": transition.id,
                "source_node_id": transition.source_node_id,
                "target_node_id": transition.target_node_id,
                "kind": transition.kind.value,
                "label": transition.label,
                "outcome": transition.outcome,
                "config": dict(transition.config),
            }
            for transition in flow.transitions
        ],
        "metadata": dict(flow.metadata),
    }


def flow_from_dict(raw: Mapping[str, Any]) -> Flow:
    _schema_version(raw)
    raw_nodes = raw.get("nodes", [])
    raw_transitions = raw.get("transitions", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_transitions, list):
        raise ProjectFormatError("Flow nodes and transitions must be arrays")
    nodes: list[Node] = []
    for index, value in enumerate(raw_nodes):
        item = _mapping(value, field=f"nodes[{index}]")
        position = _mapping(item.get("position", {}), field=f"nodes[{index}].position")
        try:
            node_type = NodeType(item.get("type"))
            x = float(position.get("x", 0.0))
            y = float(position.get("y", 0.0))
        except (TypeError, ValueError) as exc:
            raise ProjectFormatError(f"Invalid node at index {index}") from exc
        config = _mapping(item.get("config", {}), field=f"nodes[{index}].config")
        nodes.append(
            Node(
                id=_string(item.get("id"), field=f"nodes[{index}].id") or "",
                type=node_type,
                name=str(item.get("name") or ""),
                position=NodePosition(x=x, y=y),
                config=dict(config),
            )
        )
    transitions: list[Transition] = []
    for index, value in enumerate(raw_transitions):
        item = _mapping(value, field=f"transitions[{index}]")
        try:
            kind = TransitionKind(item.get("kind", TransitionKind.AUTOMATIC.value))
        except ValueError as exc:
            raise ProjectFormatError(f"Invalid transition kind at index {index}") from exc
        config = _mapping(item.get("config", {}), field=f"transitions[{index}].config")
        transitions.append(
            Transition(
                id=_string(item.get("id"), field=f"transitions[{index}].id") or "",
                source_node_id=_string(
                    item.get("source_node_id"), field=f"transitions[{index}].source_node_id"
                )
                or "",
                target_node_id=_string(
                    item.get("target_node_id"), field=f"transitions[{index}].target_node_id"
                )
                or "",
                kind=kind,
                label=_string(item.get("label"), field="label", optional=True),
                outcome=_string(item.get("outcome"), field="outcome", optional=True),
                config=dict(config),
            )
        )
    metadata = _mapping(raw.get("metadata", {}), field="metadata")
    return Flow(
        id=_string(raw.get("id"), field="id") or "",
        name=_string(raw.get("name"), field="name") or "",
        nodes=tuple(nodes),
        transitions=tuple(transitions),
        start_node_id=_string(raw.get("start_node_id"), field="start_node_id", optional=True),
        schema_version=SCHEMA_VERSION,
        metadata=dict(metadata),
    )


def dump_json(data: Mapping[str, Any]) -> str:
    return dumps_json(data, pretty=True) + "\n"


def load_json(content: str, *, source: str) -> Mapping[str, Any]:
    try:
        raw = loads_json(content)
    except ValueError as exc:
        raise ProjectFormatError(f"Invalid JSON in {source}: {exc}") from exc
    return _mapping(raw, field=source)
