from __future__ import annotations

from dataclasses import dataclass

from pipubot.domains.tutoring.calendar.oauth_service import GoogleOAuthService
from pipubot.domains.tutoring.integrations.google_calendar.client import (
    GoogleCalendarClient,
    GoogleCalendarClientConfig,
)
from pipubot.runtime.secrets import SecretsService


@dataclass(frozen=True, slots=True)
class GoogleCalendarRuntime:
    secrets: SecretsService
    google_oauth: GoogleOAuthService
    default_timeout_s: float = 20.0

    def get_calendar_id(self, profile: str) -> str:
        return self.secrets.google_calendar.get_calendar_id(profile)

    async def build_client(
        self,
        *,
        profile: str,
        timeout_s: float | None = None,
    ) -> GoogleCalendarClient:
        effective_timeout = timeout_s or self.default_timeout_s

        oauth = self.secrets.google_calendar.get_oauth_profile(profile)
        access_token = await self.google_oauth.refresh_access_token(
            client_id=oauth.client_id,
            client_secret=oauth.client_secret,
            refresh_token=oauth.refresh_token,
            timeout_s=effective_timeout,
        )

        return GoogleCalendarClient(
            GoogleCalendarClientConfig(
                access_token=access_token,
                timeout_s=effective_timeout,
            )
        )