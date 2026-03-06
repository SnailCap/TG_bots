from __future__ import annotations

from typing import Any

import httpx


class GoogleOAuthError(RuntimeError):
    pass


class GoogleOAuthService:
    def __init__(self, *, token_url: str = "https://oauth2.googleapis.com/token") -> None:
        self._token_url = token_url

    async def refresh_access_token(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        timeout_s: float = 20.0,
    ) -> str:
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(self._token_url, data=payload)
            resp.raise_for_status()

        data: Any = resp.json()
        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise GoogleOAuthError("Google OAuth response does not contain a valid access_token.")

        return access_token