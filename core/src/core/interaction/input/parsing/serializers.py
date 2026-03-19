from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TypeVar, Callable

EnumT = TypeVar("EnumT", bound=Enum)


def serialize_decimal(value: Decimal | None) -> str | None:
    """
    Convert Decimal to JSON-friendly string.
    """
    return str(value) if value is not None else None


def deserialize_decimal(value: str | None) -> Decimal | None:
    """
    Restore Decimal from serialized string.
    """
    return Decimal(value) if value is not None else None


def serialize_date(value: date | None) -> str | None:
    """
    Convert date to ISO string.
    """
    return value.isoformat() if value is not None else None


def deserialize_date(value: str | None) -> date | None:
    """
    Restore date from ISO string.
    """
    return date.fromisoformat(value) if value is not None else None


def serialize_datetime(value: datetime | None) -> str | None:
    """
    Convert datetime to ISO string.
    """
    return value.isoformat() if value is not None else None


def deserialize_datetime(value: str | None) -> datetime | None:
    """
    Restore datetime from ISO string.
    """
    return datetime.fromisoformat(value) if value is not None else None


def serialize_enum(value: Enum | None) -> str | None:
    """
    Convert enum to its value for JSON-friendly storage.
    """
    return value.value if value is not None else None


def make_enum_deserializer(enum_cls: type[EnumT]) -> Callable[[str | None], EnumT | None]:
    """
    Build deserializer that restores enum from serialized value.
    """
    def deserialize_enum(value: str | None) -> EnumT | None:
        if value is None:
            return None
        return enum_cls(value)

    return deserialize_enum