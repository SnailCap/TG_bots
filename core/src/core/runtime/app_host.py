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
    - build Telegram Application
    - initialize app
    - start plugins that prepare runtime state (DB, discovery, ASGI, background)
    - register handlers after plugins have prepared bot_data / registries
    - start PTB application and polling
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
        self._config: Final[AppConfig] = config
        self._build_application: Final = build_application
        self._register_handlers: Final = register_handlers
        self._plugins: Final[list[AppPlugin]] = list(plugins or [])

        self._app: Final[Application] = self._build_application(self._config)
        self._app.add_error_handler(self._on_error)

        self._handlers_registered: bool = False

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:  # noqa
        log.exception("Unhandled error in handler", exc_info=context.error)

    async def run_async(self) -> None:
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _request_stop() -> None:
            stop_event.set()

        for sig in (SIGINT, SIGTERM):
            try:
                loop.add_signal_handler(sig, _request_stop)  # noqa
            except NotImplementedError:
                # Windows / some environments
                pass

        try:
            # 1) initialize app first
            await self._app.initialize()

            # 2) start plugins BEFORE handler registration
            #    so plugins can prepare bot_data / registries / imports.
            for plugin in self._plugins:
                await plugin.start(self._app)
            log.info("[bot] Plugins started: %s", len(self._plugins))

            # 3) register handlers after plugins prepared runtime state
            self._register_handlers(self._app)
            self._handlers_registered = True
            log.info("[bot] Handlers registered")

            # 4) start bot
            await self._app.start()

            # 5) start polling
            await self._app.updater.start_polling(
                allowed_updates=self._config.allowed_updates or Update.ALL_TYPES,
                drop_pending_updates=self._config.drop_pending_updates,
            )
            log.info("[bot] Bot polling started")

            # 6) wait for stop signal
            await stop_event.wait()

        except asyncio.CancelledError:
            log.info("Cancelled; shutting down...")
            return

        finally:
            log.info("Shutting down...")

            for plugin in reversed(self._plugins):
                try:
                    await plugin.stop()
                except Exception:
                    log.exception("Plugin stop failed: %s", plugin)

            try:
                if self._app.updater is not None:
                    await self._app.updater.stop()
            except Exception:
                log.exception("Updater stop failed")

            try:
                await self._app.stop()
            except Exception:
                log.exception("Application stop failed")

            try:
                await self._app.shutdown()
            except Exception:
                log.exception("Application shutdown failed")

            log.info("Shutdown complete")

    def run(self) -> None:
        asyncio.run(self.run_async())