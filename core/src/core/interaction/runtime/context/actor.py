from __future__ import annotations

from dataclasses import dataclass

from .enums import UserRole


@dataclass(frozen=True, slots=True)
class InputActor:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    role: UserRole = UserRole.PUBLIC