from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, MutableMapping


@dataclass(frozen=True, slots=True)
class ActionUser:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True, slots=True)
class ActionChat:
    id: int
    type: str = "private"


@dataclass(frozen=True, slots=True)
class ActionBot:
    id: int
    username: str
    display_name: str


@dataclass(slots=True)
class ActionContext:
    project_id: str
    session_id: str
    user: ActionUser
    chat: ActionChat
    bot: ActionBot
    variables: MutableMapping[str, Any]
    logger: logging.Logger
    parameters: dict[str, Any] = field(default_factory=dict)
    services: Any = None
    telegram: Any = None
    storage: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_variable(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

    def set_variable(self, name: str, value: Any) -> None:
        if not name or not name.strip():
            raise ValueError("Variable name must not be empty")
        self.variables[name] = value
