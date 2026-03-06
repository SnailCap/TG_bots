from __future__ import annotations

from dataclasses import dataclass

from pipubot.runtime.secrets.backend import SecretBackend
from pipubot.runtime.secrets.google_calendar import GoogleCalendarSecrets


@dataclass(frozen=True, slots=True)
class SecretsService:
    """
    High-level aggregator: one entrypoint in AppServices, but grouped per integration.
    """
    backend: SecretBackend
    google_calendar: GoogleCalendarSecrets

    def get(self, key: str) -> str:
        return self.backend.get(key)

    def get_optional(self, key: str) -> str | None:
        return self.backend.get_optional(key)

    @classmethod
    def from_backend(cls, backend: SecretBackend) -> "SecretsService":
        return cls(
            backend=backend,
            google_calendar=GoogleCalendarSecrets(backend),
        )