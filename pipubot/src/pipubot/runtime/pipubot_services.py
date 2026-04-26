from __future__ import annotations

from dataclasses import dataclass

from core.runtime.services.base_runtime_services import BaseAppServices
from pipubot.domains.tutoring.calendar.oauth_service import GoogleOAuthService
from pipubot.runtime.google_calendar_runtime import GoogleCalendarRuntime
from pipubot.runtime.secrets import SecretsService


@dataclass(frozen=True, slots=True)
class PipubotServices(BaseAppServices):
    secrets: SecretsService
    google_oauth: GoogleOAuthService
    google_calendar: GoogleCalendarRuntime