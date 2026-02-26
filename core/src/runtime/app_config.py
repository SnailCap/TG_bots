from dataclasses import field, dataclass
from typing import Callable, Optional, Sequence, Any

from core.src.runtime.plugins.asgi_server_plugin import AsgiServerConfig
from core.src.runtime.plugins.background.background_service import BackgroundService


@dataclass(frozen=True, slots=True)
class AppConfig:
    bot_token: str
    config_root: str

    ui_binding_modules: Sequence[str] = field(default_factory=tuple)

    database_url: Optional[str] = None
    database_echo: bool = False

    build_background_services: Optional[
        Callable[[Any, "AppConfig"], Sequence[BackgroundService]]
    ] = None

    asgi_server: Optional[AsgiServerConfig] = None

    allowed_updates: Optional[Sequence[str]] = None
    drop_pending_updates: bool = False