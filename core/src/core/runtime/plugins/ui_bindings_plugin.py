from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Iterable, Sequence

from core.runtime.plugins.app_plugin import AppPlugin

logger = logging.getLogger(__name__)


class UiBindingImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class UiBindingsPlugin(AppPlugin):
    """
    Imports user modules/packages that register UI classes via decorator side effects.

    Contract:
    - Each item in `targets` may be:
        1) a module (e.g. "pipubot.ui.ui_bindings")
        2) a package (e.g. "pipubot.ui.components") — then ALL submodules are imported recursively
    - Registration happens via side effects at import time.
    """

    targets: Sequence[str]

    async def start(self, app: Any) -> None:  # noqa: ARG002
        normalized = tuple(t.strip() for t in (self.targets or ()) if t and t.strip())
        if not normalized:
            logger.info("UiBindingsPlugin: no targets configured; skipping.")
            return

        imported: list[str] = []
        for target in normalized:
            try:
                imported.extend(self._import_target(target))
            except Exception as e:
                raise UiBindingImportError(
                    f"Failed to import UI bindings target '{target}'. "
                    f"Check your bindings list and project structure."
                ) from e

        logger.info("UiBindingsPlugin: imported %d module(s).", len(imported))
        logger.debug("UiBindingsPlugin: imported modules: %s", ", ".join(imported))

    async def stop(self) -> None:
        # Nothing to clean up; registry lives for process lifetime.
        return

    # -------------------------
    # internals
    # -------------------------
    def _import_target(self, target: str) -> list[str]:
        root = importlib.import_module(target)
        imported: list[str] = [root.__name__]

        if self._is_package(root):
            for name in self._iter_submodules(root):
                importlib.import_module(name)
                imported.append(name)

        return imported

    @staticmethod
    def _is_package(mod: ModuleType) -> bool:
        return hasattr(mod, "__path__")

    @staticmethod
    def _iter_submodules(pkg: ModuleType) -> Iterable[str]:
        prefix = pkg.__name__ + "."
        for mod_info in pkgutil.walk_packages(pkg.__path__, prefix=prefix):
            yield mod_info.name