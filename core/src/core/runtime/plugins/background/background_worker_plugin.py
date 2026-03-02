from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Final, Sequence, TYPE_CHECKING

from core.runtime.plugins.app_plugin import AppPlugin
from core.runtime.plugins.background.background_service import BackgroundService
from core.shared.utils.module_importer import import_target_tree

if TYPE_CHECKING:
    from core.runtime.app_config import AppConfig

log = logging.getLogger(__name__)


class BackgroundHandlersImportError(RuntimeError):
    pass


class BackgroundServicesPlugin(AppPlugin):
    """
    Runs one or many background services with:
      - async run_forever()
      - stop()

    Optional:
      - import handler modules/packages before starting services (side-effect registration).
    """

    def __init__(
        self,
        *,
        config: "AppConfig",
        build_services: Callable[[Any, "AppConfig"], Sequence[BackgroundService]],
        handler_modules: Sequence[str] | None = None,
    ) -> None:
        self._config: Final = config
        self._build_services: Final = build_services
        self._handler_modules: Final = tuple(handler_modules or ())
        self._services: list[BackgroundService] = []
        self._tasks: list[asyncio.Task] = []

    async def start(self, app: Any) -> None:
        await self._import_handlers_if_needed()

        self._services = list(self._build_services(app, self._config) or [])
        for i, svc in enumerate(self._services):
            task = asyncio.create_task(svc.run_forever(), name=f"background-service-{i}")
            self._tasks.append(task)

        log.info("Background services started: %s", len(self._services))

    async def stop(self) -> None:
        for svc in self._services:
            try:
                svc.stop()
            except Exception:
                log.exception("Background service stop() failed: %s", svc)

        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks = []
        self._services = []
        log.info("Background services stopped")

    async def _import_handlers_if_needed(self) -> None:
        normalized = tuple(t.strip() for t in self._handler_modules if t and t.strip())
        if not normalized:
            log.info("BackgroundServicesPlugin: no handler modules configured; skipping imports.")
            return

        imported: list[str] = []
        for target in normalized:
            try:
                imported.extend(import_target_tree(target))
            except Exception as e:
                raise BackgroundHandlersImportError(
                    f"Failed to import background handlers target '{target}'. "
                    f"Check your handler modules list and project structure."
                ) from e

        log.info("BackgroundServicesPlugin: imported %d handler module(s).", len(imported))
        log.debug("BackgroundServicesPlugin: imported handler modules: %s", ", ".join(imported))