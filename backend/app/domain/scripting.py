from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ActionParameter:
    name: str
    annotation: str | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class ScriptAction:
    name: str
    module: str
    file_path: str
    line: int
    is_async: bool
    parameters: tuple[ActionParameter, ...] = ()
    docstring: str | None = None


@dataclass(frozen=True, slots=True)
class Condition:
    id: str
    kind: str = "expression"
    expression: str | None = None
    action_name: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

