from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping


def _normalize_key(key: Any) -> str:
    if isinstance(key, Enum):
        return str(key.value)
    return str(key)


@dataclass(frozen=True, slots=True)
class ConfigItem:
    key: str
    payload: dict[str, Any]
    source_path: Path


@dataclass(frozen=True, slots=True)
class ConfigIndex:
    group: str
    items: Mapping[str, ConfigItem]

    def keys(self) -> list[str]:
        return list(self.items.keys())

    def get(self, key: Any) -> dict[str, Any] | None:
        key_s = _normalize_key(key)
        item = self.items.get(key_s)
        return item.payload if item else None

    def require(self, key: Any) -> dict[str, Any]:
        key_s = _normalize_key(key)
        item = self.items.get(key_s)
        if item is None:
            raise KeyError(f"Config key not found in group '{self.group}': {key_s}")
        return item.payload

    def source(self, key: Any) -> Path | None:
        key_s = _normalize_key(key)
        item = self.items.get(key_s)
        return item.source_path if item else None

    def __contains__(self, key: Any) -> bool:
        return _normalize_key(key) in self.items

    def __len__(self) -> int:
        return len(self.items)