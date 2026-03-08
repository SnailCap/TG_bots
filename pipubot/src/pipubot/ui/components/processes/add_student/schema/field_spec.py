from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeAlias


FieldParser: TypeAlias = Callable[[str], Any]
FieldFormatter: TypeAlias = Callable[[Any], str]
FieldSerializer: TypeAlias = Callable[[Any], Any]
FieldDeserializer: TypeAlias = Callable[[Any], Any]
FieldValidator: TypeAlias = Callable[[Any], str | None]


def default_formatter(value: Any) -> str:
    return "—" if value is None else str(value)


def identity_serializer(value: Any) -> Any:
    return value


def identity_deserializer(value: Any) -> Any:
    return value


@dataclass(frozen=True, slots=True)
class StudentFieldSpec:
    field_name: str
    label: str
    aliases: tuple[str, ...]
    parser: FieldParser

    required: bool = False
    allow_positional: bool = False
    include_in_confirm: bool = True

    formatter: FieldFormatter = default_formatter
    serializer: FieldSerializer = identity_serializer
    deserializer: FieldDeserializer = identity_deserializer
    validator: FieldValidator | None = None