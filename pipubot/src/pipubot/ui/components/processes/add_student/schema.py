from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, TypeAlias


FieldParser: TypeAlias = Callable[[str], Any]
FieldFormatter: TypeAlias = Callable[[Any], str]
FieldSerializer: TypeAlias = Callable[[Any], Any]
FieldDeserializer: TypeAlias = Callable[[Any], Any]
FieldValidator: TypeAlias = Callable[[Any], str | None]


def parse_text(value: str) -> str:
    return value.strip()


def parse_decimal(value: str) -> Decimal | None:
    normalized = value.strip().replace(",", ".")
    if not normalized:
        return None

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_int(value: str) -> int | None:
    normalized = value.strip()
    if not normalized:
        return None

    try:
        return int(normalized)
    except ValueError:
        return None


def format_default(value: Any) -> str:
    return "—" if value is None else str(value)


def serialize_identity(value: Any) -> Any:
    return value


def deserialize_identity(value: Any) -> Any:
    return value


def serialize_decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def deserialize_decimal(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def validate_positive_decimal(value: Decimal | None) -> str | None:
    if value is not None and value <= 0:
        return "Ставка должна быть больше 0."
    return None


def validate_positive_int(value: int | None) -> str | None:
    if value is not None and value <= 0:
        return "Длительность должна быть больше 0 минут."
    return None


@dataclass(frozen=True, slots=True)
class StudentFieldSpec:
    field_name: str
    label: str
    aliases: tuple[str, ...]
    parser: FieldParser

    required: bool = False
    allow_positional: bool = True
    include_in_confirm: bool = True

    formatter: FieldFormatter = format_default
    serializer: FieldSerializer = serialize_identity
    deserializer: FieldDeserializer = deserialize_identity
    validator: FieldValidator | None = None


STUDENT_FIELD_SPECS: tuple[StudentFieldSpec, ...] = (
    StudentFieldSpec(
        field_name="full_name",
        label="Имя",
        aliases=("имя", "name", "фио", "full_name"),
        parser=parse_text,
        required=True,
    ),
    StudentFieldSpec(
        field_name="default_rate",
        label="Ставка",
        aliases=("ставка", "rate", "цена"),
        parser=parse_decimal,
        required=True,
        serializer=serialize_decimal,
        deserializer=deserialize_decimal,
        validator=validate_positive_decimal,
    ),
    StudentFieldSpec(
        field_name="default_duration_min",
        label="Длительность",
        aliases=("длительность", "длительность урока", "duration", "minutes"),
        parser=parse_int,
        validator=validate_positive_int,
    ),
    StudentFieldSpec(
        field_name="telegram_username",
        label="Telegram username",
        aliases=("юзер", "telegram_username"),
        parser=parse_text,
    ),
    StudentFieldSpec(
        field_name="telegram_link",
        label="Telegram ссылка",
        aliases=("ссылка на телеграм", "telegram link", "telegram"),
        parser=parse_text,
    ),
    StudentFieldSpec(
        field_name="email",
        label="Email",
        aliases=("почта", "email"),
        parser=parse_text,
    ),
    StudentFieldSpec(
        field_name="notes",
        label="Заметки",
        aliases=("заметки", "notes"),
        parser=parse_text,
        allow_positional=False,
    ),
    StudentFieldSpec(
        field_name="default_currency",
        label="Валюта",
        aliases=("валюта", "currency"),
        parser=parse_text,
    ),
)

FIELD_SPEC_BY_NAME: dict[str, StudentFieldSpec] = {
    spec.field_name: spec
    for spec in STUDENT_FIELD_SPECS
}

ALIAS_TO_FIELD_NAME: dict[str, str] = {
    alias.strip().lower(): spec.field_name
    for spec in STUDENT_FIELD_SPECS
    for alias in spec.aliases
}

POSITIONAL_FIELD_ORDER: tuple[str, ...] = tuple(
    spec.field_name
    for spec in STUDENT_FIELD_SPECS
    if spec.allow_positional
)