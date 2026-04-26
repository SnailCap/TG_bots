from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BotDataKeys:
    services: str = "runtime.services"
    db_engine: str = "runtime.db.engine"
    db_session_maker: str = "runtime.db.session_maker"