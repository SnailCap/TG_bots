from __future__ import annotations

import logging
from typing import Callable, Sequence

from telegram.ext import Application

from core.runtime.app_config import AppConfig
from core.runtime.app_host import AppHost
from core.runtime.plugins.app_plugin import AppPlugin
from core.runtime.plugins.background.background_worker_plugin import BackgroundServicesPlugin
from core.runtime.plugins.ui_bindings_plugin import UiBindingsPlugin

log = logging.getLogger(__name__)


def build_plugins(
    config: AppConfig,
    *,
    build_application: Callable[[AppConfig], Application],
) -> list[AppPlugin]:
    plugins: list[AppPlugin] = []

    if config.ui_binding_modules:
        plugins.append(UiBindingsPlugin(config.ui_binding_modules))

    # Background services (optional)
    if config.build_background_services is not None:
        plugins.append(
            BackgroundServicesPlugin(
                config=config,
                build_services=config.build_background_services,
            )
        )

    # ASGI server (optional)
    if config.asgi_server is not None:
        from core.runtime.plugins.asgi_server_plugin import AsgiServerPlugin

        plugins.append(AsgiServerPlugin(config=config.asgi_server, build_application=build_application))  # type: ignore

    return plugins


def run_app(
    config: AppConfig,
    *,
    build_application: Callable[[AppConfig], Application],
    register_handlers: Callable[[Application], None],
    plugins: Sequence[AppPlugin] | None = None,
) -> None:
    auto_plugins = build_plugins(config, build_application=build_application)
    all_plugins = list(plugins or []) + auto_plugins

    host = AppHost(
        config,
        build_application=build_application,
        register_handlers=register_handlers,
        plugins=all_plugins,
    )
    host.run()