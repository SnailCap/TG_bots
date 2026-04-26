from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Final, Sequence

from telegram.ext import Application

from core.db.providers.sqlalchemy_session_provider import SqlAlchemySessionProvider
from core.interaction.adapters.ptb.messenger import PtbMessenger
from core.interaction.adapters.ptb.update_dispatcher import UpdateDispatcher
from core.interaction.config.api import build_config_loader
from core.interaction.contracts.start_page_resolver import StartPageResolver
from core.interaction.config.paths import ResourcePaths
from core.interaction.routing.user_input_router import UserInputRouter
from core.interaction.ui.build.renderable_builder import RenderableBuilder
from core.interaction.ui.build.ui_builder import UiBuilder
from core.runtime.app_config import AppConfig
from core.runtime.builders.built_runtime import BuiltRuntime
from core.runtime.context.runtime_context import RuntimeContext
from core.runtime.plugins.app_plugin import AppPlugin
from core.runtime.plugins.asgi_server_plugin import AsgiServerConfig, AsgiServerPlugin
from core.runtime.plugins.background.background_service import BackgroundService
from core.runtime.plugins.background.background_worker_plugin import (
    BackgroundServicesPlugin,
)
from core.runtime.plugins.convention_discovery_plugin import ConventionDiscoveryPlugin
from core.runtime.plugins.db_plugin import DbPlugin
from core.runtime.plugins.ui_bindings_plugin import UiBindingsPlugin
from core.runtime.services.base_runtime_services import (
    BaseAppServices,
    BaseInteractionServices,
)
from core.services.notifications.loggers.notification_log_db import DbNotificationLog
from core.services.notifications.notification_service import NotificationService


BuildApplication = Callable[[AppConfig], Application]
RegisterHandlersHook = Callable[[Application], None]
ServicesExtender = Callable[[BaseAppServices], Any]


@dataclass(slots=True)
class _AssemblyState:
    ui_builder: UiBuilder | None = None
    router: UserInputRouter | None = None
    identity_provider: Any | None = None


@dataclass(slots=True)
class BotRuntimeBuilder:
    config: AppConfig
    _build_application: BuildApplication | None = None
    _register_hooks: list[RegisterHandlersHook] = field(default_factory=list)
    _plugins: list[AppPlugin] = field(default_factory=list)
    _services_extender: ServicesExtender | None = None
    _state: _AssemblyState = field(default_factory=_AssemblyState)

    # ------------------------------------------------------------------
    # low-level
    # ------------------------------------------------------------------

    def with_application_builder(
        self,
        builder: BuildApplication,
    ) -> "BotRuntimeBuilder":
        self._build_application = builder
        return self

    def with_register_hook(
        self,
        hook: RegisterHandlersHook,
    ) -> "BotRuntimeBuilder":
        self._register_hooks.append(hook)
        return self

    def with_plugin(self, plugin: AppPlugin) -> "BotRuntimeBuilder":
        self._plugins.append(plugin)
        return self

    def with_plugins(self, *plugins: AppPlugin) -> "BotRuntimeBuilder":
        self._plugins.extend(plugins)
        return self

    # ------------------------------------------------------------------
    # discovery
    # ------------------------------------------------------------------

    def with_standard_discovery(self) -> "BotRuntimeBuilder":
        root_package = getattr(self.config, "root_package", None)
        if root_package and root_package.strip():
            self._plugins.append(ConventionDiscoveryPlugin(root_package=root_package))
        return self

    # ------------------------------------------------------------------
    # standard runtime pieces
    # ------------------------------------------------------------------

    def with_ptb(self) -> "BotRuntimeBuilder":
        def _build_application(config: AppConfig) -> Application:
            return Application.builder().token(config.bot_token).build()

        self._build_application = _build_application
        return self

    def with_db(self) -> "BotRuntimeBuilder":
        self._plugins.append(DbPlugin(self.config))
        return self

    def with_ui_bindings(self, *targets: str) -> "BotRuntimeBuilder":
        normalized = tuple(t.strip() for t in targets if t and t.strip())
        if normalized:
            self._plugins.append(UiBindingsPlugin(normalized))
        return self

    def with_background_workers(
        self,
        *,
        build_services: Callable[[Any, AppConfig], Sequence[BackgroundService]],
        handler_modules: Sequence[str] | None = None,
    ) -> "BotRuntimeBuilder":
        self._plugins.append(
            BackgroundServicesPlugin(
                config=self.config,
                build_services=build_services,
                handler_modules=handler_modules,
            )
        )
        return self

    def with_asgi(self, asgi_config: AsgiServerConfig) -> "BotRuntimeBuilder":
        self._plugins.append(AsgiServerPlugin(asgi_config))
        return self

    def with_plugins_from_config(self) -> "BotRuntimeBuilder":
        if self.config.database_url:
            self.with_db()

        root_package = getattr(self.config, "root_package", None)
        if root_package and root_package.strip():
            self.with_standard_discovery()
        else:
            if self.config.ui_binding_modules:
                self.with_ui_bindings(*self.config.ui_binding_modules)

        if self.config.build_background_services is not None:
            self.with_background_workers(
                build_services=self.config.build_background_services,
                handler_modules=self.config.background_handler_modules,
            )

        if self.config.asgi_server is not None:
            self.with_asgi(self.config.asgi_server)

        return self

    # ------------------------------------------------------------------
    # interaction assembly
    # ------------------------------------------------------------------

    def with_standard_interaction(
        self,
        *,
        start_page_resolver: StartPageResolver | None = None,
    ) -> "BotRuntimeBuilder":
        paths = ResourcePaths.from_root(self.config.config_root).normalized()
        loader = build_config_loader(self.config.config_root)
        renderable_builder = RenderableBuilder(loader=loader)

        ui_builder = UiBuilder(
            paths=paths,
            loader=loader,
            renderable_builder=renderable_builder,
        )
        router = UserInputRouter(ui=ui_builder, start_page=start_page_resolver)

        self._state.ui_builder = ui_builder
        self._state.router = router
        return self

    def with_identity(self, provider: Any) -> "BotRuntimeBuilder":
        self._state.identity_provider = provider
        return self

    def extend_services(
        self,
        extender: ServicesExtender,
    ) -> "BotRuntimeBuilder":
        self._services_extender = extender
        return self

    def with_runtime_services(self) -> "BotRuntimeBuilder":
        @dataclass(slots=True)
        class _RuntimeServicesPlugin(AppPlugin):
            builder: "BotRuntimeBuilder"

            async def start(self, app: Application) -> None:
                if self.builder._state.ui_builder is None:
                    raise RuntimeError(
                        "UI builder is not configured. Call .with_standard_interaction() first."
                    )

                if self.builder._state.identity_provider is None:
                    raise RuntimeError(
                        "Identity provider is not configured. Call .with_identity(...) first."
                    )

                runtime = RuntimeContext(app)
                messenger = PtbMessenger(app.bot)

                notification_service = NotificationService(
                    ui=self.builder._state.ui_builder,
                    messenger=messenger,  # type: ignore[arg-type]
                    notification_log=DbNotificationLog(),  # type: ignore[arg-type]
                )

                interaction_services = BaseInteractionServices(
                    ui=self.builder._state.ui_builder,
                    messenger=messenger,  # type: ignore[arg-type]
                    notification_service=notification_service,
                )

                base_services = BaseAppServices(
                    interaction=interaction_services,
                    identity=self.builder._state.identity_provider,
                )

                final_services = (
                    self.builder._services_extender(base_services)
                    if self.builder._services_extender is not None
                    else base_services
                )

                runtime.set_services(final_services)

            async def stop(self) -> None:
                return

        self._plugins.append(_RuntimeServicesPlugin(self))
        return self

    def with_dispatcher(self) -> "BotRuntimeBuilder":
        def _hook(app: Application) -> None:
            if self._state.router is None:
                raise RuntimeError(
                    "Router is not configured. Call .with_standard_interaction() first."
                )

            if self._state.identity_provider is None:
                raise RuntimeError(
                    "Identity provider is not configured. Call .with_identity(...) first."
                )

            runtime = RuntimeContext(app)

            if not runtime.has_session_maker():
                raise RuntimeError(
                    "DB session maker is not available in bot_data. "
                    "Call .with_db() or .with_plugins_from_config() with database_url."
                )

            if not runtime.has_services():
                raise RuntimeError(
                    "Runtime services are not available in runtime context. "
                    "Call .with_runtime_services() before startup."
                )

            services = runtime.get_services()
            messenger = services.interaction.messenger

            session_provider = SqlAlchemySessionProvider(
                session_maker=runtime.get_session_maker()
            )

            dispatcher = UpdateDispatcher(
                router=self._state.router,
                session_provider=session_provider,  # type: ignore[arg-type]
                identity_provider=self._state.identity_provider,
                messenger=messenger,  # type: ignore[arg-type]
            )
            dispatcher.register_handlers(app)

        self._register_hooks.append(_hook)
        return self

    # ------------------------------------------------------------------
    # build
    # ------------------------------------------------------------------

    def build(self) -> BuiltRuntime:
        if self._build_application is None:
            raise RuntimeError(
                "Application builder is not configured. Call .with_ptb() "
                "or .with_application_builder(...)."
            )

        build_application: Final[BuildApplication] = self._build_application
        register_hooks: Final[tuple[RegisterHandlersHook, ...]] = tuple(self._register_hooks)
        plugins: Final[tuple[AppPlugin, ...]] = tuple(self._plugins)

        def _register_handlers(app: Application) -> None:
            for hook in register_hooks:
                hook(app)

        return BuiltRuntime(
            config=self.config,
            build_application=build_application,
            register_handlers=_register_handlers,
            plugins=plugins,
        )
