from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from telegram.ext import Application

from core.runtime.app_config import AppConfig
from core.runtime.app_host import AppHost
from core.runtime.plugins.app_plugin import AppPlugin


@dataclass(frozen=True, slots=True)
class BuiltRuntime:
    config: AppConfig
    build_application: Callable[[AppConfig], Application]
    register_handlers: Callable[[Application], None]
    plugins: Sequence[AppPlugin]

    def run(self) -> None:
        host = AppHost(
            self.config,
            build_application=self.build_application,
            register_handlers=self.register_handlers,
            plugins=list(self.plugins),
        )
        host.run()