from __future__ import annotations

from dataclasses import dataclass

from pipubot.runtime.secrets.backend import SecretBackend


@dataclass(frozen=True, slots=True)
class GoogleOAuthProfile:
    client_id: str
    client_secret: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class GoogleCalendarSecrets:
    backend: SecretBackend

    def get_oauth_profile(self, profile: str) -> GoogleOAuthProfile:
        """
        profile example: "KONSTANTIN" -> reads:
          GCAL_KONSTANTIN_CLIENT_ID
          GCAL_KONSTANTIN_CLIENT_SECRET
          GCAL_KONSTANTIN_REFRESH_TOKEN
        """
        p = _normalize_profile(profile)
        prefix = f"GCAL_{p}"
        return GoogleOAuthProfile(
            client_id=self.backend.require_non_empty(f"{prefix}_CLIENT_ID"),
            client_secret=self.backend.require_non_empty(f"{prefix}_CLIENT_SECRET"),
            refresh_token=self.backend.require_non_empty(f"{prefix}_REFRESH_TOKEN"),
        )

    def get_calendar_id(self, profile: str, *, default: str = "primary") -> str:
        """
        Optional config-like value (not a secret), but convenient to keep nearby.
        Reads: GCAL_<PROFILE>_CALENDAR_ID, fallback to default.
        """
        p = _normalize_profile(profile)
        key = f"GCAL_{p}_CALENDAR_ID"
        return self.backend.get_optional(key) or default


def _normalize_profile(profile: str) -> str:
    # allow "gcal.konstantin", "konstantin", "KONSTANTIN"
    p = profile.strip().upper().replace(".", "_").replace("-", "_")
    # if user passes already "GCAL_KONSTANTIN", tolerate it:
    if p.startswith("GCAL_"):
        p = p[len("GCAL_") :]
    return p