from __future__ import annotations

from typing import Callable, Optional, Sequence

from telegram.ext import Application

from core.runtime.app_config import AppConfig
from core.runtime.app_host import AppHost
from core.runtime.plugins.app_plugin import AppPlugin
from core.runtime.plugins.ui_bindings_plugin import UiBindingsPlugin
from core.runtime.plugins.db_plugin import DbPlugin
from core.runtime.plugins.background.background_worker_plugin import BackgroundServicesPlugin


def default_plugins(config: AppConfig) -> list[AppPlugin]:
    plugins: list[AppPlugin] = [
        UiBindingsPlugin(config),
        DbPlugin(config),
    ]

    if config.build_background_services is not None:
        plugins.append(
            BackgroundServicesPlugin(
                config=config,
                build_services=config.build_background_services,
            )
        )

    return plugins


def run_app(
        config: AppConfig,
        *,
        build_application: Callable[[AppConfig], Application],
        register_handlers: Callable[[Application], None],
        plugins: Optional[Sequence[AppPlugin]] = None,
) -> None:
    # ... existing code ...
    host = AppHost(
        config,
        build_application=build_application,
        register_handlers=register_handlers,
        plugins=list(plugins) if plugins is not None else default_plugins(config),
    )
    host.run()