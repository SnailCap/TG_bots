from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.src.interaction.config.errors import (
    ConfigRootNotFound,
    ConfigStructureError,
    RequiredConfigDirMissing,
)
from core.src.interaction.config.paths import ResourcePaths


@dataclass(frozen=True, slots=True)
class ConfigStructureValidator:
    """
    Валидирует обязательные директории конфига.

    Обязательные:
    - buttons/, notifications/, pages/, steps/
    - text/
    - text/pages, text/steps, text/notifications

    Внутреннюю структуру (вложенные подпапки/файлы) не проверяет.
    """

    def validate(self, paths: ResourcePaths) -> None:
        root: Path = paths.root

        if not root.exists():
            raise ConfigRootNotFound(f"Config root does not exist: {root}")

        if not root.is_dir():
            raise ConfigStructureError(f"Config root is not a directory: {root}")

        required_dirs: dict[str, Path] = {}
        required_dirs.update(paths.anchor_dirs())

        # text root
        required_dirs["text"] = paths.text_dir
        # entity-specific text dirs
        required_dirs.update({f"text/{k}": v for k, v in paths.text_dirs().items()})

        missing: list[str] = []
        not_dirs: list[str] = []

        for name, dir_path in required_dirs.items():
            if not dir_path.exists():
                missing.append(f"{name} -> {dir_path}")
                continue
            if not dir_path.is_dir():
                not_dirs.append(f"{name} -> {dir_path}")

        if missing or not_dirs:
            parts: list[str] = []
            if missing:
                parts.append("Missing required config directories:\n- " + "\n- ".join(missing))
            if not_dirs:
                parts.append("These paths exist but are not directories:\n- " + "\n- ".join(not_dirs))
            raise RequiredConfigDirMissing("\n\n".join(parts))
