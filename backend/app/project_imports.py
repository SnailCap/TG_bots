from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

_RESERVED_ROOTS = {"app", "bot_engine"}


def _project_roots(scripts_root: Path) -> set[str]:
    if not scripts_root.is_dir():
        return set()
    roots: set[str] = set()
    for child in scripts_root.iterdir():
        if child.name == "__pycache__":
            continue
        if child.is_dir():
            roots.add(child.name)
        elif child.is_file() and child.suffix == ".py" and child.stem != "__init__":
            roots.add(child.stem)
    return roots - _RESERVED_ROOTS


@contextmanager
def isolated_project_imports(scripts_root: Path) -> Iterator[None]:
    """Temporarily isolate import names that can resolve inside one project.

    Imported module objects remain referenced by action function globals, while
    their generic names are removed afterwards so another project can safely
    use its own ``helper.py`` or package with the same name.
    """

    root = scripts_root.resolve()
    names = _project_roots(root)

    def is_project_name(module_name: str) -> bool:
        top_level = module_name.partition(".")[0]
        return top_level in names

    previous: dict[str, ModuleType] = {
        name: module
        for name, module in tuple(sys.modules.items())
        if module is not None and is_project_name(name)
    }
    for name in previous:
        sys.modules.pop(name, None)

    old_path = list(sys.path)
    sys.path.insert(0, str(root))
    try:
        yield
    finally:
        sys.path[:] = old_path
        for name in tuple(sys.modules):
            if is_project_name(name):
                sys.modules.pop(name, None)
        sys.modules.update(previous)
