from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from core.shared.utils.session_helper import create_engine, create_session_maker
from core.runtime.app_config import AppConfig

log = logging.getLogger(__name__)

BOT_DATA_ENGINE_KEY = "db_engine"
BOT_DATA_SESSION_MAKER_KEY = "db_session_maker"


@dataclass(slots=True)
class DbPlugin:
    config: AppConfig
    _engine: Optional[AsyncEngine]

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def start(self, app: Any) -> None:  # NOSONAR
        if not self.config.database_url:
            log.info("DbPlugin: database_url is not set; skipping DB init.")
            return

        self._engine = create_engine(self.config.database_url, echo=self.config.database_echo)
        app.bot_data[BOT_DATA_ENGINE_KEY] = self._engine
        app.bot_data[BOT_DATA_SESSION_MAKER_KEY] = create_session_maker(self._engine)

        log.info("DbPlugin: DB initialized")

    async def stop(self) -> None:
        if self._engine is not None:
            try:
                await self._engine.dispose()
            except Exception:
                log.exception("DbPlugin: engine.dispose() failed")
        self._engine = None
