from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.interaction.config.errors import (
    ConfigDuplicateKeyError,
    ConfigJsonParseError,
    ConfigLoadError,
    ConfigNotAJsonObjectError,
)
from core.interaction.config.index import ConfigIndex, ConfigItem
from core.interaction.config.paths import ResourcePaths
from core.interaction.config.types import GroupName


@dataclass(slots=True)
class ConfigLoader:
    """
    Загружает конфиги внутри одной группы.

    Контракт файла:
      - каждый *.json содержит JSON object (dict)
      - верхний уровень: <key>: <payload_object>
      - payload для каждого key тоже должен быть dict

    Пример:
    {
      "public_home": { ... },
      "admin_home":  { ... }
    }

    - Уникальность ключей проверяется внутри группы.
    - Одинаковый key между группами допустим.
    """

    paths: ResourcePaths
    _cache: dict[str, ConfigIndex] = field(default_factory=dict, init=False, repr=False)

    def load_group(self, group: GroupName, *, force_reload: bool = False) -> ConfigIndex:
        if not force_reload and group in self._cache:
            return self._cache[group]

        base_dir = self._group_dir(group)
        items: dict[str, ConfigItem] = {}

        for path in self._iter_json_files(base_dir):
            mapping = self._read_json_object(path)

            for key, payload in mapping.items():
                if not isinstance(key, str) or not key.strip():
                    raise ConfigLoadError(f"Top-level key must be a non-empty string in file: {path}")

                if not isinstance(payload, dict):
                    raise ConfigLoadError(
                        f"Value for key '{key}' must be a JSON object in file: {path}"
                    )

                key_s = key.strip()

                if key_s in items:
                    prev = items[key_s].source_path
                    raise ConfigDuplicateKeyError(
                        f"Duplicate key '{key_s}' in group '{group}'.\n"
                        f"- First:  {prev}\n"
                        f"- Second: {path}"
                    )

                items[key_s] = ConfigItem(key=key_s, payload=payload, source_path=path)

        index = ConfigIndex(group=group, items=items)
        self._cache[group] = index
        return index

    def load_pages(self, *, force_reload: bool = False) -> ConfigIndex:
        return self.load_group("pages", force_reload=force_reload)

    def load_steps(self, *, force_reload: bool = False) -> ConfigIndex:
        return self.load_group("steps", force_reload=force_reload)

    def load_buttons(self, *, force_reload: bool = False) -> ConfigIndex:
        return self.load_group("buttons", force_reload=force_reload)

    def load_notifications(self, *, force_reload: bool = False) -> ConfigIndex:
        return self.load_group("notifications", force_reload=force_reload)

    def invalidate(self, group: GroupName) -> None:
        self._cache.pop(group, None)

    def invalidate_all(self) -> None:
        self._cache.clear()

    # ---------- internals ----------
    def _group_dir(self, group: GroupName) -> Path:
        return self.paths.anchor_dirs()[group]

    def _iter_json_files(self, base_dir: Path):
        yield from sorted(base_dir.rglob("*.json"))

    def _read_json_object(self, path: Path) -> dict[str, Any]:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            raise ConfigLoadError(f"Failed to read file: {path}. {e}") from e

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ConfigJsonParseError(f"Invalid JSON in file: {path}. {e}") from e

        if not isinstance(data, dict):
            raise ConfigNotAJsonObjectError(
                f"Config file must contain a JSON object at top level: {path}"
            )

        return data