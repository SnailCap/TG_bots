from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.project import RecentProject

from .paths import atomic_write_text


class JsonRecentProjectsRepository:
    def __init__(self, path: Path, *, limit: int = 20) -> None:
        self._path = path.expanduser().resolve(strict=False)
        self._limit = max(1, limit)

    def list(self) -> tuple[RecentProject, ...]:
        entries = tuple(self._load())
        return tuple(
            replace(entry, exists=Path(entry.path).expanduser().is_dir()) for entry in entries
        )

    def add(self, project: RecentProject) -> None:
        entries = [entry for entry in self._load() if entry.project_id != project.project_id]
        entries.insert(0, project)
        self._save(entries[: self._limit])

    def remove(self, project_id: str) -> None:
        self._save([entry for entry in self._load() if entry.project_id != project_id])

    def _load(self) -> list[RecentProject]:
        if not self._path.is_file():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("schema_version") != 1:
                return []
            values = raw.get("projects", [])
            if not isinstance(values, list):
                return []
            result: list[RecentProject] = []
            for value in values:
                if not isinstance(value, dict):
                    continue
                result.append(self._decode(value))
            return result
        except (OSError, ValueError, TypeError, KeyError):
            return []

    def _save(self, entries: list[RecentProject]) -> None:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "projects": [
                {
                    "project_id": entry.project_id,
                    "name": entry.name,
                    "path": entry.path,
                    "last_opened_at": entry.last_opened_at.isoformat(),
                }
                for entry in entries
            ],
        }
        atomic_write_text(
            self._path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    @staticmethod
    def _decode(value: dict[str, Any]) -> RecentProject:
        return RecentProject(
            project_id=str(value["project_id"]),
            name=str(value["name"]),
            path=str(value["path"]),
            last_opened_at=datetime.fromisoformat(str(value["last_opened_at"])),
        )

