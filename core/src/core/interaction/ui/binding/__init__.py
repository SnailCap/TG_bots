from __future__ import annotations

from .decorators import get_default_ui_registry
from .resolver import UiClassResolver

__all__ = [
    "UiClassResolver",
    "get_default_ui_registry",
]