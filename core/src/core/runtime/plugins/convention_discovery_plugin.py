from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any, Final

from core.runtime.plugins.app_plugin import AppPlugin
from core.shared.utils.module_importer import import_target_tree

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConventionDiscoveryPlugin(AppPlugin):
    """
    Convention-based import discovery for project modules that rely on
    decorator side effects for registration.

    Standard zones:
      - <root_package>.ui
      - <root_package>.background.handlers
      - <root_package>.background.handler

    Missing zones are ignored.
    """

    root_package: str

    async def start(self, app: Any) -> None:  # noqa: ARG002
        root = self.root_package.strip()
        if not root:
            log.info("ConventionDiscoveryPlugin: empty root_package; skipping.")
            return

        targets: Final[tuple[str, ...]] = (
            f"{root}.ui",
            f"{root}.background.handlers",
            f"{root}.background.handler",
        )

        imported: list[str] = []
        for target in targets:
            imported.extend(self._try_import_target(target))

        log.info(
            "ConventionDiscoveryPlugin: imported %d module(s) from standard zones.",
            len(imported),
        )
        if imported:
            log.debug(
                "ConventionDiscoveryPlugin: imported modules: %s",
                ", ".join(imported),
            )

    async def stop(self) -> None:
        return

    def _try_import_target(self, target: str) -> list[str]:
        try:
            importlib.import_module(target)
        except ModuleNotFoundError as e:
            # Ignore only when the missing module is exactly the target root.
            # If a nested import inside the package failed, re-raise.
            if e.name == target:
                log.debug(
                    "ConventionDiscoveryPlugin: target '%s' not found; skipping.",
                    target,
                )
                return []
            raise

        return list(import_target_tree(target))