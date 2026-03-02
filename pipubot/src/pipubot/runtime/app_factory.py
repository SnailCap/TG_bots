from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final

from telegram.ext import Application

from core.db.providers.sqlalchemy_session_provider import SqlAlchemySessionProvider
from core.interaction.adapters.ptb.update_dispatcher import UpdateDispatcher
from core.interaction.config.api import build_config_loader
from core.interaction.config.paths import ResourcePaths
from core.interaction.routing.user_input_router import UserInputRouter
from core.interaction.ui.builders.renderable_builder import RenderableBuilder
from core.interaction.ui.builders.ui_builder import PtbUiBuilder
from core.runtime.app_config import AppConfig
from core.services.identity.provider import DbIdentityProvider
from core.shared.utils.session_helper import create_engine, create_session_maker

from pipubot.background.build_services import build_background_services
from pipubot.bindings import PIPUBOT_UI_BINDINGS
from pipubot.runtime.run_app import run_app


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass(frozen=True, slots=True)
class BuiltApp:
    config: AppConfig
    build_application: Callable[[AppConfig], Application]
    register_handlers: Callable[[Application], None]

    def run(self) -> None:
        run_app(
            self.config,
            build_application=self.build_application,
            register_handlers=self.register_handlers,
        )


class PipubotAppFactory:
    """
    pipubot-specific assembly point.
    """

    def __init__(self, *, config: AppConfig) -> None:
        self._config: Final = config

        if not self._config.database_url:
            raise RuntimeError("DATABASE_URL is not set. Please set env var DATABASE_URL.")

        # --- DB ---
        self._engine = create_engine(self._config.database_url, echo=self._config.database_echo)
        self._session_maker = create_session_maker(self._engine)
        self._session_provider = SqlAlchemySessionProvider(session_maker=self._session_maker)

        # --- UI/config ---
        paths = ResourcePaths.from_root(self._config.config_root).normalized()
        loader = build_config_loader(self._config.config_root)

        renderable_builder = RenderableBuilder(loader=loader)
        ui_builder = PtbUiBuilder(paths=paths, loader=loader, renderable_builder=renderable_builder)
        router = UserInputRouter(ui=ui_builder)

        # --- Identity ---
        identity_provider = DbIdentityProvider()

        self._dispatcher = UpdateDispatcher(
            router=router,
            session_provider=self._session_provider,
            identity_provider=identity_provider,
        )

    # callbacks for AppHost
    def build_application(self, config: AppConfig) -> Application:
        return Application.builder().token(config.bot_token).build()

    def register_handlers(self, app: Application) -> None:
        # expose session_maker for background plugin
        app.bot_data["session_maker"] = self._session_maker
        self._dispatcher.register_handlers(app)

    def build(self) -> BuiltApp:
        return BuiltApp(
            config=self._config,
            build_application=self.build_application,
            register_handlers=self.register_handlers,
        )

    @classmethod
    def from_env(cls) -> BuiltApp:
        _setup_logging()

        config_root = str(Path(__file__).resolve().parents[3] / "resources" / "config")

        config = AppConfig(
            bot_token=os.environ["BOT_TOKEN"],
            config_root=config_root,
            # ✅ Centralized list lives in pipubot/bindings.py
            ui_binding_modules=tuple(PIPUBOT_UI_BINDINGS.packages),
            database_url=os.environ.get("DATABASE_URL"),
            build_background_services=build_background_services,
        )
        return cls(config=config).build()