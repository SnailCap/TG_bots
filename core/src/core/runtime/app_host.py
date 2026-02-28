from __future__ import annotations

import asyncio
import logging
from signal import SIGINT, SIGTERM
from typing import Callable, Final, Optional, Sequence

from telegram import Update
from telegram.ext import Application, ContextTypes

from core.runtime.app_config import AppConfig
from core.runtime.plugins.app_plugin import AppPlugin

log = logging.getLogger(__name__)


class AppHost:
    """
    Framework-level runtime host for PTB + asyncio:
    - start PTB application and polling
    - start/stop plugins (background worker, asgi server, etc.)
    - graceful shutdown on SIGINT/SIGTERM
    """

    def __init__(
        self,
        config: AppConfig,
        *,
        build_application: Callable[[AppConfig], Application],
        register_handlers: Callable[[Application], None],
        plugins: Optional[Sequence[AppPlugin]] = None,
    ) -> None:
        self._config: Final = config
        self._build_application: Final = build_application
        self._register_handlers: Final = register_handlers
        self._plugins: Final[list[AppPlugin]] = list(plugins or [])

        self._app: Final[Application] = self._build_application(self._config)
        self._app.add_error_handler(self._on_error)

        # register handlers after the application exists
        self._register_handlers(self._app)

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa
        log.exception("Unhandled error in handler", exc_info=context.error)

    async def run_async(self) -> None:
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _request_stop() -> None:
            stop_event.set()

        for sig in (SIGINT, SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_stop) # noqa
            except NotImplementedError:
                # Windows / some environments
                pass

        try:
            # 1) init + start bot
            await self._app.initialize()
            await self._app.start()

            # 2) polling
            await self._app.updater.start_polling(
                allowed_updates=self._config.allowed_updates or Update.ALL_TYPES,
                drop_pending_updates=self._config.drop_pending_updates,
            )
            log.info("[bot] Bot polling started")

            # 3) plugins start
            for p in self._plugins:
                await p.start(self._app)
            log.info("[bot] Plugins started: %s", len(self._plugins))

            # 4) wait stop
            await stop_event.wait()

        except asyncio.CancelledError:
            # Stop/IDE shutdown cancels the main task -> treat as normal exit (no scary traceback)
            log.info("Cancelled; shutting down...")
            return

        finally:
            # 5) shutdown
            log.info("Shutting down...")

            for p in reversed(self._plugins):
                try:
                    await p.stop()
                except Exception:
                    log.exception("Plugin stop failed: %s", p)

            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            log.info("Shutdown complete")

    def run(self) -> None:
        asyncio.run(self.run_async())