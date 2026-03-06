from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, Final

from telegram.ext import Application

from core.db.providers.sqlalchemy_session_provider import SqlAlchemySessionProvider
from core.interaction.adapters.ptb.messenger import PtbMessenger
from core.interaction.adapters.ptb.update_dispatcher import UpdateDispatcher
from core.interaction.config.api import build_config_loader
from core.interaction.config.paths import ResourcePaths
from core.interaction.routing.user_input_router import UserInputRouter
from core.interaction.ui.build.renderable_builder import RenderableBuilder
from core.interaction.ui.build.ui_builder import UiBuilder
from core.runtime.app_config import AppConfig
from core.runtime.app_host import AppHost
from core.runtime.plugins.app_plugin import AppPlugin
from core.runtime.plugins.background.background_worker_plugin import BackgroundServicesPlugin
from core.runtime.plugins.ui_bindings_plugin import UiBindingsPlugin
from core.services.identity.provider import DbIdentityProvider
from core.services.notifications.loggers.notification_log_db import DbNotificationLog
from core.services.notifications.notification_service import NotificationService
from core.shared.utils.session_helper import create_engine, create_session_maker

from pipubot.background.binding.bindings import BG_HANDLER_TARGETS
from core.background.build_services import build_background_services
from pipubot.domains.tutoring.services.gcal.google_oauth_service import GoogleOAuthService
from pipubot.paths.main_paths import PipubotPaths
from pipubot.runtime.runtime_services import DefaultAppServices, DefaultInteractionServices
from pipubot.runtime.secrets import EnvSecretBackend, SecretsService
from pipubot.ui.binding.bindings import UI_BINDINGS

BOT_DATA_SESSION_MAKER: Final[str] = "session_maker"
BOT_DATA_SERVICES: Final[str] = "services"


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
    build_plugins: Callable[[AppConfig], list[AppPlugin]]

    def run(self) -> None:
        plugins = self.build_plugins(self.config)

        host = AppHost(
            self.config,
            build_application=self.build_application,
            register_handlers=self.register_handlers,
            plugins=plugins,
        )
        host.run()


class PipubotAppFactory:
    """
    Project-specific assembly point.

    - __init__: build-time wiring (DB, UI builder, router, identity)
    - register_handlers: runtime wiring (messenger and services)
    - build_plugins: plugin assembly
    """

    def __init__(self, *, config: AppConfig) -> None:
        self._config: Final[AppConfig] = config

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
        self._ui_builder = UiBuilder(paths=paths, loader=loader, renderable_builder=renderable_builder)
        self._router = UserInputRouter(ui=self._ui_builder)

        # --- Identity ---
        self._identity_provider = DbIdentityProvider()

    # ------------------------------------------------------------------
    # Application lifecycle
    # ------------------------------------------------------------------

    def build_application(self, config: AppConfig) -> Application:
        return Application.builder().token(config.bot_token).build()

    def register_handlers(self, app: Application) -> None:
        app.bot_data[BOT_DATA_SESSION_MAKER] = self._session_maker

        messenger = PtbMessenger(app.bot)

        notification_log = DbNotificationLog()
        notification_service = NotificationService(
            ui=self._ui_builder,
            messenger=messenger, # type: ignore
            notification_log=notification_log, # type: ignore
        )
        secret_backend = EnvSecretBackend()
        secrets = SecretsService.from_backend(secret_backend)
        google_oauth = GoogleOAuthService()
        interaction_services = DefaultInteractionServices(
            ui=self._ui_builder,
            messenger=messenger, # type: ignore
            notification_service=notification_service,
        )

        services: DefaultAppServices = DefaultAppServices(
            interaction=interaction_services,
            identity=self._identity_provider,
            secrets=secrets,
            google_oauth=google_oauth,
        )
        app.bot_data[BOT_DATA_SERVICES] = services

        dispatcher = UpdateDispatcher(
            router=self._router,
            session_provider=self._session_provider, # type: ignore
            identity_provider=self._identity_provider,
            messenger=messenger, # type: ignore
        )
        dispatcher.register_handlers(app)

    # ------------------------------------------------------------------
    # Plugin assembly
    # ------------------------------------------------------------------

    def build_plugins(self, config: AppConfig) -> list[AppPlugin]:
        plugins: list[AppPlugin] = []

        if config.ui_binding_modules:
            plugins.append(UiBindingsPlugin(config.ui_binding_modules))

        if config.build_background_services is not None:
            plugins.append(
                BackgroundServicesPlugin(
                    config=config,
                    build_services=config.build_background_services,
                    handler_modules=config.background_handler_modules,
                )
            )

        return plugins

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> BuiltApp:
        return BuiltApp(
            config=self._config,
            build_application=self.build_application,
            register_handlers=self.register_handlers,
            build_plugins=self.build_plugins,
        )

    @classmethod
    def from_env(cls) -> BuiltApp:
        _setup_logging()

        paths = PipubotPaths.from_file(__file__)

        config = AppConfig(
            bot_token=os.environ["BOT_TOKEN"],
            config_root=paths.config_root,
            ui_binding_modules=tuple(UI_BINDINGS.packages),
            database_url=os.environ.get("DATABASE_URL"),
            build_background_services=build_background_services,
            background_handler_modules=tuple(BG_HANDLER_TARGETS.packages),
            recurring_prefix="system."
        )

        return cls(config=config).build()
