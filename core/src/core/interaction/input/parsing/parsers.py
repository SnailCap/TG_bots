from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Callable, TypeVar

from .enum_utils import normalize_enum_lookup_key

EnumT = TypeVar("EnumT", bound=Enum)


def parse_str(value: str) -> str:
    """
    Trimmed string parser.
    """
    return value.strip()


def parse_non_empty_str(value: str) -> str:
    """
    Trimmed non-empty string parser.
    """
    result = value.strip()
    if not result:
        raise ValueError("Значение не должно быть пустым.")
    return result


def parse_int(value: str) -> int:
    """
    Parse integer from text.
    """
    try:
        return int(value.strip())
    except ValueError as e:
        raise ValueError("Ожидалось целое число.") from e


def parse_float(value: str) -> float:
    """
    Parse float from text, allowing comma as decimal separator.
    """
    normalized = value.strip().replace(",", ".")
    try:
        return float(normalized)
    except ValueError as e:
        raise ValueError("Ожидалось число.") from e


def parse_decimal(value: str) -> Decimal:
    """
    Parse Decimal from text, allowing comma as decimal separator.
    """
    normalized = value.strip().replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError) as e:
        raise ValueError("Ожидалось число.") from e


def parse_bool(value: str) -> bool:
    """
    Parse bool from human-friendly text.
    """
    normalized = value.strip().lower()

    true_values = {"true", "1", "yes", "y", "да", "д", "on"}
    false_values = {"false", "0", "no", "n", "нет", "н", "off"}

    if normalized in true_values:
        return True
    if normalized in false_values:
        return False

    raise ValueError("Ожидалось логическое значение: да/нет, true/false, 1/0.")


def parse_date_iso(value: str) -> date:
    """
    Parse date in YYYY-MM-DD format.
    """
    try:
        return date.fromisoformat(value.strip())
    except ValueError as e:
        raise ValueError("Ожидалась дата в формате YYYY-MM-DD.") from e


def parse_datetime_iso(value: str) -> datetime:
    """
    Parse datetime in ISO format.
    """
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as e:
        raise ValueError("Ожидалась дата/время в ISO-формате.") from e


def make_enum_parser(
    lookup: dict[str, EnumT],
    *,
    field_label: str,
) -> Callable[[str], EnumT]:
    """
    Build parser for enum-like values using normalized alias lookup.
    """
    def parse_enum(raw: str) -> EnumT:
        key = normalize_enum_lookup_key(raw)

        try:
            return lookup[key]
        except KeyError as e:
            allowed = ", ".join(sorted(lookup.keys()))
            raise ValueError(
                f"{field_label}: неизвестное значение '{raw}'. "
                f"Допустимые варианты: {allowed}"
            ) from e

    return parse_enum