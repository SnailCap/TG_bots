from __future__ import annotations

from enum import Enum
from typing import Iterable, TypeVar

EnumT = TypeVar("EnumT", bound=Enum)


def normalize_enum_lookup_key(value: str) -> str:
    """
    Normalize human-entered enum aliases for robust lookup.

    Examples:
        "  Широкий  " -> "широкий"
        "Ё" -> "е"
    """
    return value.strip().lower().replace("ё", "е")


def build_enum_alias_lookup(
    *,
    canonical_pairs: Iterable[tuple[str, EnumT]],
    aliases: dict[str, EnumT] | None = None,
) -> dict[str, EnumT]:
    """
    Build normalized lookup dictionary for enum parsing.

    canonical_pairs:
        Base names that should always resolve.

    aliases:
        Additional synonyms / localized variants.
    """
    result: dict[str, EnumT] = {}

    for key, enum_value in canonical_pairs:
        result[normalize_enum_lookup_key(key)] = enum_value

    for key, enum_value in (aliases or {}).items():
        result[normalize_enum_lookup_key(key)] = enum_value

    return result