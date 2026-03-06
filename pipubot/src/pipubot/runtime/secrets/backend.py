from __future__ import annotations

from typing import Protocol, runtime_checkable

from pipubot.runtime.secrets.errors import SecretValueError


@runtime_checkable
class SecretBackend(Protocol):
    """
    Low-level access to secrets by key.

    Rules:
    - get() must raise SecretNotFoundError if key missing.
    - get_optional() returns None if missing.
    """

    def get(self, key: str) -> str: ...
    def get_optional(self, key: str) -> str | None: ...

    def require_non_empty(self, key: str) -> str: ...
    def require_int(self, key: str) -> int: ...


class SecretBackendMixin:
    """
    Optional helper mixin to avoid repeating common validators.
    Backends may inherit this mixin (not required).
    """

    def require_non_empty(self, key: str) -> str:
        value = self.get(key)
        if not value.strip():
            raise SecretValueError(key, "value is empty")
        return value

    def require_int(self, key: str) -> int:
        raw = self.require_non_empty(key)
        try:
            return int(raw)
        except ValueError as exc:
            raise SecretValueError(key, "expected integer") from exc