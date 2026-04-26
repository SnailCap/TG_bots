from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.shared.utils.file_path_helper import parent, file_path, as_posix_str


@dataclass(frozen=True, slots=True)
class PipubotPaths:
    repo_root: Path

    @classmethod
    def from_file(cls, file: str) -> "PipubotPaths":
        # src/pipubot/... -> repo root is 4 levels above the module file
        return cls(repo_root=parent(file_path(file), 4))

    @property
    def resources_root(self) -> Path:
        return self.repo_root / "resources"

    @property
    def config_root(self) -> str:
        return as_posix_str(self.resources_root / "config")
