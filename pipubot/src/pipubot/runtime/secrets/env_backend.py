from __future__ import annotations

import os

from pipubot.runtime.secrets.backend import SecretBackendMixin
from pipubot.runtime.secrets.errors import SecretNotFoundError


class EnvSecretBackend(SecretBackendMixin):
    """
    Reads secrets from environment variables.
    """

    def get(self, key: str) -> str:
        try:
            return os.environ[key]
        except KeyError as exc:
            raise SecretNotFoundError(key) from exc

    def get_optional(self, key: str) -> str | None:
        return os.environ.get(key)