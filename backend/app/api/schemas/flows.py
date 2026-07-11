from __future__ import annotations

from pydantic import Field

from app.domain.enums import NodeType, TransitionKind
from app.domain.flow import Flow, Node, NodePosition, Transition

from .common import ApiModel


class PositionPayload(ApiModel):
    x: float = 0.0
    y: float = 0.0


class NodePayload(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    type: NodeType
    name: str = ""
    position: PositionPayload = PositionPayload()
    config: dict = {}


class TransitionPayload(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    source_node_id: str = Field(min_length=1, max_length=128)
    target_node_id: str = Field(min_length=1, max_length=128)
    kind: TransitionKind = TransitionKind.AUTOMATIC
    label: str | None = None
    outcome: str | None = None
    config: dict = {}


class FlowPayload(ApiModel):
    schema_version: int = 1
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    start_node_id: str | None = None
    nodes: list[NodePayload] = []
    transitions: list[TransitionPayload] = []
    metadata: dict = {}


class CreateFlowRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)


def flow_from_payload(value: FlowPayload) -> Flow:
    return Flow(
        id=value.id,
        name=value.name,
        start_node_id=value.start_node_id,
        schema_version=value.schema_version,
        nodes=tuple(
            Node(
                id=node.id,
                type=NodeType(node.type),
                name=node.name,
                position=NodePosition(x=node.position.x, y=node.position.y),
                config=dict(node.config),
            )
            for node in value.nodes
        ),
        transitions=tuple(
            Transition(
                id=item.id,
                source_node_id=item.source_node_id,
                target_node_id=item.target_node_id,
                kind=TransitionKind(item.kind),
                label=item.label,
                outcome=item.outcome,
                config=dict(item.config),
            )
            for item in value.transitions
        ),
        metadata=dict(value.metadata),
    )


def flow_payload(value: Flow) -> FlowPayload:
    return FlowPayload(
        schema_version=value.schema_version,
        id=value.id,
        name=value.name,
        start_node_id=value.start_node_id,
        nodes=[
            NodePayload(
                id=node.id,
                type=node.type,
                name=node.name,
                position=PositionPayload(x=node.position.x, y=node.position.y),
                config=dict(node.config),
            )
            for node in value.nodes
        ],
        transitions=[
            TransitionPayload(
                id=item.id,
                source_node_id=item.source_node_id,
                target_node_id=item.target_node_id,
                kind=item.kind,
                label=item.label,
                outcome=item.outcome,
                config=dict(item.config),
            )
            for item in value.transitions
        ],
        metadata=dict(value.metadata),
    )

