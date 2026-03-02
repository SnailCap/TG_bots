from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Iterable


def import_target_tree(target: str) -> list[str]:
    """
    Import a module or recursively import all submodules of a package.

    Returns list of imported module names.
    """
    root = importlib.import_module(target)
    imported: list[str] = [root.__name__]

    if _is_package(root):
        for name in _iter_submodules(root):
            importlib.import_module(name)
            imported.append(name)

    return imported


def _is_package(mod: ModuleType) -> bool:
    return hasattr(mod, "__path__")


def _iter_submodules(pkg: ModuleType) -> Iterable[str]:
    prefix = pkg.__name__ + "."
    for mod_info in pkgutil.walk_packages(pkg.__path__, prefix=prefix):
        yield mod_info.name