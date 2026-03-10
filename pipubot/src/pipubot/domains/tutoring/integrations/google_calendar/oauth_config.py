from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    refresh_token: str