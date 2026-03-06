from dataclasses import field, dataclass
from typing import Callable, Optional, Sequence, Any

from core.runtime.plugins.asgi_server_plugin import AsgiServerConfig
from core.runtime.plugins.background.background_service import BackgroundService


@dataclass(frozen=True, slots=True)
class AppConfig:
    bot_token: str
    config_root: str

    # UI bindings (side effect imports)
    ui_binding_modules: Sequence[str] = field(default_factory=tuple)

    database_url: Optional[str] = None
    database_echo: bool = False

    # Background services builder (optional)
    build_background_services: Optional[
        Callable[[Any, "AppConfig"], Sequence[BackgroundService]]
    ] = None

    # Background recurring bootstrap
    bootstrap_recurring: bool = True
    recurring_prefix: str = "system."

    # Background task handlers (side effect imports)
    background_handler_modules: Sequence[str] = field(default_factory=tuple)

    # Optional: validate that all expected handlers are registered at startup
    validate_background_handlers: bool = True

    asgi_server: Optional[AsgiServerConfig] = None

    allowed_updates: Optional[Sequence[str]] = None
    drop_pending_updates: bool = False
