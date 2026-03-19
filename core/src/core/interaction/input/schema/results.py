from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

ObjectT = TypeVar("ObjectT")


@dataclass(frozen=True, slots=True)
class InputValues:
    """
    Normalized values extracted from some raw input format.
    """
    values: dict[str, Any] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return not self.values


@dataclass(frozen=True, slots=True)
class InputParseResult:
    """
    Result of parsing raw input into normalized field values.
    """
    data: InputValues
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class ObjectBuildResult(Generic[ObjectT]):
    """
    Result of building or patching a typed object.
    """
    obj: ObjectT
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors