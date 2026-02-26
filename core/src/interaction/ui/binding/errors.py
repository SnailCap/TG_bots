from __future__ import annotations


class UiBindingError(RuntimeError):
    """Base error for UI binding subsystem."""


class DuplicateBindingError(UiBindingError):
    """Same key is registered twice for the same entity kind."""


class InvalidBindingError(UiBindingError):
    """Invalid class passed to decorator / registration."""
