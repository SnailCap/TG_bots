from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Final, Sequence, TYPE_CHECKING

from core.runtime.plugins.app_plugin import AppPlugin
from core.runtime.plugins.background.background_service import BackgroundService

if TYPE_CHECKING:
    from core.runtime.app_config import AppConfig

log = logging.getLogger(__name__)


class BackgroundServicesPlugin(AppPlugin):
    """
    Runs one or many background services with:
      - async run_forever()
      - stop()
    """

    def __init__(
        self,
        *,
        config: "AppConfig",
        build_services: Callable[[Any, "AppConfig"], Sequence[BackgroundService]],
    ) -> None:
        self._config: Final = config
        self._build_services: Final = build_services
        self._services: list[BackgroundService] = []
        self._tasks: list[asyncio.Task] = []

    async def start(self, app: Any) -> None:
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