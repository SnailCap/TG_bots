from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GoogleOAuthError(RuntimeError):
    """Base Google OAuth error."""


class GoogleOAuthReauthRequiredError(GoogleOAuthError):
    """Refresh token is invalid/revoked, and the user must re-authorize."""


class GoogleOAuthService:
    def __init__(
        self,
        *,
        token_url: str = "https://oauth2.googleapis.com/token",
    ) -> None:
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

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(self._token_url, data=payload)
        except httpx.HTTPError as exc:
            raise GoogleOAuthError(f"Google OAuth request failed: {exc}") from exc

        if resp.is_error:
            error_code, error_description = self._extract_google_error(resp)

            logger.error(
                "Google OAuth token refresh failed: status=%s error=%s description=%s body=%s",
                resp.status_code,
                error_code,
                error_description,
                resp.text,
            )

            if error_code == "invalid_grant":
                raise GoogleOAuthReauthRequiredError(
                    "Google refresh token is invalid or revoked; re-authorization is required."
                )

            if error_code == "invalid_client":
                raise GoogleOAuthError(
                    "Google OAuth client credentials are invalid."
                )

            raise GoogleOAuthError(
                f"Google OAuth token refresh failed: status={resp.status_code}, "
                f"error={error_code!r}, description={error_description!r}"
            )

        data: Any = resp.json()
        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            raise GoogleOAuthError(
                "Google OAuth response does not contain a valid access_token."
            )

        return access_token

    @staticmethod
    def _extract_google_error(resp: httpx.Response) -> tuple[str | None, str | None]:
        try:
            data = resp.json()
        except ValueError:
            return None, resp.text

        if not isinstance(data, dict):
            return None, resp.text

        error = data.get("error")
        description = data.get("error_description")

        return (
            error if isinstance(error, str) else None,
            description if isinstance(description, str) else None,
        )