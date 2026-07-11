from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.domain.enums import ActionResultStatus
from app.domain.runtime import RuntimeResult


@dataclass(frozen=True, slots=True)
class ActionResult:
    status: ActionResultStatus
    next_transition: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        *,
        next_transition: str | None = None,
        variables: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionResult":
        return cls(
            status=ActionResultStatus.SUCCESS,
            next_transition=next_transition,
            variables=dict(variables or {}),
            metadata=dict(metadata or {}),
        )

    @classmethod
    def error_result(
        cls,
        message: str,
        *,
        next_transition: str | None = "error",
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionResult":
        return cls(
            status=ActionResultStatus.ERROR,
            next_transition=next_transition,
            error_message=message,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def error(
        cls,
        message: str,
        *,
        next_transition: str | None = "error",
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionResult":
        return cls.error_result(
            message,
            next_transition=next_transition,
            metadata=metadata,
        )

    @classmethod
    def branch(
        cls,
        transition: str,
        *,
        variables: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ActionResult":
        if not transition.strip():
            raise ValueError("Branch transition must not be empty")
        return cls(
            status=ActionResultStatus.BRANCH,
            next_transition=transition,
            variables=dict(variables or {}),
            metadata=dict(metadata or {}),
        )

    def to_runtime_result(self) -> RuntimeResult:
        return RuntimeResult(
            status=self.status,
            next_transition=self.next_transition,
            variables=dict(self.variables),
            error=self.error_message,
            metadata=dict(self.metadata),
        )
