from __future__ import annotations

from app.errors import SecretStoreError


class KeyringSecretStore:
    def __init__(self, *, service_name: str = "telegram-bot-studio") -> None:
        self._service_name = service_name

    def set(self, reference: str, value: str) -> None:
        if not reference.strip() or not value:
            raise ValueError("Secret reference and value must not be empty")
        try:
            import keyring

            keyring.set_password(self._service_name, reference, value)
        except Exception as exc:
            raise SecretStoreError("System secret storage is unavailable") from exc

    def get(self, reference: str) -> str | None:
        try:
            import keyring

            return keyring.get_password(self._service_name, reference)
        except Exception as exc:
            raise SecretStoreError("System secret storage is unavailable") from exc

    def delete(self, reference: str) -> None:
        try:
            import keyring
            from keyring.errors import PasswordDeleteError

            try:
                keyring.delete_password(self._service_name, reference)
            except PasswordDeleteError:
                return
        except SecretStoreError:
            raise
        except Exception as exc:
            raise SecretStoreError("System secret storage is unavailable") from exc

