from __future__ import annotations

from enum import Enum
from typing import Any


def normalize_key(value: Any) -> str:
    """
    Canonical key representation for the interaction layer.

    Rules:
    - Enum -> Enum.value
    - other -> as-is string conversion
    """
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)