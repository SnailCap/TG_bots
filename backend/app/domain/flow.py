from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .enums import NodeType, TransitionKind


@dataclass(frozen=True, slots=True)
class NodePosition:
    x: float = 0.0
    y: float = 0.0


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    type: NodeType
    name: str = ""
    position: NodePosition = field(default_factory=NodePosition)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Transition:
    id: str
    source_node_id: str
    target_node_id: str
    kind: TransitionKind = TransitionKind.AUTOMATIC
    label: str | None = None
    outcome: str | None = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Flow:
    id: str
    name: str
    nodes: tuple[Node, ...] = ()
    transitions: tuple[Transition, ...] = ()
    start_node_id: str | None = None
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, name: str) -> "Flow":
        normalized = name.strip()
        if not normalized:
            raise ValueError("Flow name must not be empty")
        return cls(id=str(uuid4()), name=normalized)

