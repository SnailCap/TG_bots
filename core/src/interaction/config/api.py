from __future__ import annotations

from pathlib import Path

from .loader import ConfigLoader
from .paths import ResourcePaths
from .structure_validator import ConfigStructureValidator


def build_config_loader(config_root: str | Path) -> ConfigLoader:
    paths = ResourcePaths.from_root(config_root).normalized()
    ConfigStructureValidator().validate(paths)
    return ConfigLoader(paths=paths)
