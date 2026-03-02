from __future__ import annotations

from typing import Callable, Sequence

from telegram.ext import Application

from core.runtime.app_config import AppConfig
from core.runtime.app_host import AppHost
from core.runtime.plugins.app_plugin import AppPlugin


def run_app(
    config: AppConfig,
    *,
    build_application: Callable[[AppConfig], Application],
    register_handlers: Callable[[Application], None],
    plugins: Sequence[AppPlugin] | None = None,
) -> None:
    host = AppHost(
        config,
        build_application=build_application,
        register_handlers=register_handlers,
        plugins=list(plugins or []),
    )
    host.run()