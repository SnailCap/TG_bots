from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from .enums import SessionStatus, VariableType
from .project import utc_now


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    value: Any
    type: VariableType = VariableType.JSON


@dataclass(frozen=True, slots=True)
class InputExpectation:
    variable_name: str
    expected_type: VariableType = VariableType.STRING
    required: bool = True
    attempts: int = 0
    max_attempts: int = 3
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class Session:
    id: str
    project_id: str
    telegram_user_id: int
    telegram_chat_id: int
    flow_id: str
    current_node_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    variables: dict[str, Any] = field(default_factory=dict)
    waiting_for_input: InputExpectation | None = None
    flow_schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        telegram_user_id: int,
        telegram_chat_id: int,
        flow_id: str,
        current_node_id: str,
    ) -> "Session":
        return cls(
            id=str(uuid4()),
            project_id=project_id,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=telegram_chat_id,
            flow_id=flow_id,
            current_node_id=current_node_id,
        )

