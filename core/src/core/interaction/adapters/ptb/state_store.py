from __future__ import annotations
from typing import Any

from core.shared.utils.enum_helpers import unwrap_enum


class PtbUserDataStateStore:
    def __init__(self, user_data: dict) -> None:
        self._user_data = user_data

    def set(self, key: Any, value: Any) -> None:
        self._user_data[unwrap_enum(key)] = unwrap_enum(value)

    def get(self, key: Any, default: Any = None) -> Any:
        return self._user_data.get(unwrap_enum(key), default)

    def pop(self, key: Any, default: Any = None) -> Any:
        return self._user_data.pop(unwrap_enum(key), default)

    def has(self, key: Any) -> bool:
        return unwrap_enum(key) in self._user_data

    def dump(self) -> dict:
        return dict(self._user_data)
