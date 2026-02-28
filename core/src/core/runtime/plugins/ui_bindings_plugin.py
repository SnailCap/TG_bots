from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Iterable, Sequence

from core.runtime.app_config import AppConfig

logger = logging.getLogger(__name__)


class UiBindingImportError(RuntimeError):
    pass


@dataclass(slots=True)
class UiBindingsPlugin:
    """
    Импортирует пользовательские модули/пакеты, которые регистрируют UI классы через декораторы.

    Контракт:
    - Каждый элемент AppConfig.ui_binding_modules может быть:
        1) модулем (e.g. "ui.ui_bindings")
        2) пакетом (e.g. "ui.components") — тогда импортируются ВСЕ подмодули рекурсивно
    - Регистрация происходит через side-effect декораторов при импорте.
    """

    config: AppConfig

    async def start(self, app: Any) -> None:  # noqa
        targets: Sequence[str] = tuple(self.config.ui_binding_modules or ())
        if not targets:
            logger.info("UiBindingsPlugin: no ui_binding_modules configured; skipping.")
            return

        imported: list[str] = []
        for target in targets:
            try:
                imported.extend(self._import_target(target))
            except Exception as e:
                raise UiBindingImportError(
                    f"Failed to import ui bindings target '{target}'. "
                    f"Check AppConfig.ui_binding_modules and your project structure."
                ) from e

        if imported:
            logger.info("UiBindingsPlugin: imported %d module(s).", len(imported))
            logger.debug("UiBindingsPlugin: imported modules: %s", ", ".join(imported))

    async def stop(self) -> None:
        # Ничего не делаем: registry живёт на процесс
        return

    # -------------------------
    # internals
    # -------------------------
    def _import_target(self, target: str) -> list[str]:
        """
        Импортирует либо модуль, либо (если это пакет) все подмодули.
        Возвращает список реально импортированных модулей (включая корневой).
        """
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