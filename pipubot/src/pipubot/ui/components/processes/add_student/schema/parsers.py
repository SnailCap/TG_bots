from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, TypeVar

from .enum_aliases import normalize_enum_lookup_key

EnumT = TypeVar("EnumT", bound=Enum)


def parse_text(value: str) -> str:
    return value.strip()


def parse_decimal(value: str) -> Decimal | None:
    normalized = value.strip().replace(",", ".")
    if not normalized:
        return None

    try:
        return Decimal(normalized)
    except InvalidOperation as e:
        raise ValueError("должно быть числом") from e


def parse_int(value: str) -> int | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        return int(normalized)
    except ValueError as e:
        raise ValueError("должно быть целым числом") from e


def parse_date_iso(value: str) -> date | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        return date.fromisoformat(normalized)
    except ValueError as e:
        raise ValueError("должно быть датой в формате YYYY-MM-DD") from e


def make_enum_parser(
    enum_cls: type[EnumT],
    *,
    field_label: str,
    aliases: dict[str, EnumT] | None = None,
) -> Callable[[str], EnumT | None]:
    aliases = aliases or {}

    normalized_aliases = {
        normalize_enum_lookup_key(key): enum_value
        for key, enum_value in aliases.items()
    }

    def parser(value: str) -> EnumT | None:
        normalized = value.strip()
        if not normalized:
            return None

        lookup_key = normalize_enum_lookup_key(normalized)

        alias_match = normalized_aliases.get(lookup_key)
        if alias_match is not None:
            return alias_match

        for member in enum_cls:
            if normalize_enum_lookup_key(member.name) == lookup_key:
                return member

            member_value = member.value
            if isinstance(member_value, str):
                if normalize_enum_lookup_key(member_value) == lookup_key:
                    return member

        allowed_values = ", ".join(
            str(member.value) if isinstance(member.value, str) else member.name
            for member in enum_cls
        )
        raise ValueError(
            f"неизвестное значение для поля «{field_label}». "
            f"Допустимые значения: {allowed_values}"
        )

    return parser


def format_default(value: Any) -> str:
    return "—" if value is None else str(value)


def format_enum(value: Enum | None) -> str:
    if value is None:
        return "—"

    if isinstance(value.value, str):
        return value.value

    return value.name


def serialize_identity(value: Any) -> Any:
    return value


def deserialize_identity(value: Any) -> Any:
    return value


def serialize_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def deserialize_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def serialize_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def deserialize_date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def make_enum_serializer() -> Callable[[Enum | None], str | None]:
    def serializer(value: Enum | None) -> str | None:
        return None if value is None else value.name

    return serializer


def make_enum_deserializer(
    enum_cls: type[EnumT],
) -> Callable[[str | None], EnumT | None]:
    def deserializer(value: str | None) -> EnumT | None:
        if value is None:
            return None
        return enum_cls[value]

    return deserializer


def validate_positive_decimal(value: Decimal | None) -> str | None:
    if value is not None and value <= 0:
        return "Значение должно быть больше 0."
    return None


def validate_positive_int(value: int | None) -> str | None:
    if value is not None and value <= 0:
        return "Значение должно быть больше 0."
    return None