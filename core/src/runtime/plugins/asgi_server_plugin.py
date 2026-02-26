from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

import uvicorn

from core.src.runtime.plugins.app_plugin import AppPlugin

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AsgiServerConfig:
    app: str  # e.g. "mybot.external.stripe.webhook:app"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"


class AsgiServerPlugin(AppPlugin):
    """
    Runs uvicorn server in the same asyncio loop as the bot.
    """

    def __init__(self, config: AsgiServerConfig) -> None:
        self._config = config
        self._server: Optional[uvicorn.Server] = None
        self._task: Optional[asyncio.Task] = None

    async def start(self, app: Any) -> None:
        uv_config = uvicorn.Config(
            self._config.app,
            host=self._config.host,
            port=self._config.port,
            log_level=self._config.log_level,
            workers=1,
            loop="asyncio",
        )
        self._server = uvicorn.Server(uv_config)
        self._task = asyncio.create_task(self._server.serve(), name="asgi-server")
        log.info("ASGI server started on %s:%s", self._config.host, self._config.port)

    async def stop(self) -> None:
        if self._server is None:
            return

        self._server.should_exit = True

        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

        self._task = None
        self._server = None
        log.info("ASGI server stopped")
