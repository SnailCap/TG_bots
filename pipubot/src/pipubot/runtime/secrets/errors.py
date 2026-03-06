from __future__ import annotations


class SecretError(RuntimeError):
    pass


class SecretNotFoundError(SecretError):
    def __init__(self, key: str) -> None:
        super().__init__(f"Secret not found: {key}")
        self.key = key


class SecretValueError(SecretError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"Invalid secret value for {key}: {message}")
        self.key = key