from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Iterable, TypeVar

from core.interaction.input.parsing.enum_utils import build_enum_alias_lookup
from core.interaction.input.schema import FieldSpec
from core.interaction.input.parsing import (
    make_enum_parser,
    parse_bool,
    parse_date_iso,
    parse_datetime_iso,
    parse_decimal,
    parse_int,
    parse_non_empty_str,
    parse_str,
)
from core.interaction.input.parsing import (
    deserialize_date,
    deserialize_datetime,
    deserialize_decimal,
    make_enum_deserializer,
    serialize_date,
    serialize_datetime,
    serialize_decimal,
    serialize_enum,
)

ObjectT = TypeVar("ObjectT")
EnumT = TypeVar("EnumT", bound=Enum)


def text(
    name: str,
    label: str,
    *,
    required: bool = False,
    non_empty: bool | None = None,
    validator=None,
) -> FieldSpec[ObjectT, str]:
    parser = parse_non_empty_str if (required or non_empty) else parse_str
    return FieldSpec.build(
        name=name,
        label=label,
        required=required,
        parser=parser,
        validator=validator,
    )


def int_field(
    name: str,
    label: str,
    *,
    required: bool = False,
    validator=None,
) -> FieldSpec[ObjectT, int]:
    return FieldSpec.build(
        name=name,
        label=label,
        required=required,
        parser=parse_int,
        validator=validator,
    )


def decimal_field(
    name: str,
    label: str,
    *,
    required: bool = False,
    validator=None,
) -> FieldSpec[ObjectT, Decimal]:
    return FieldSpec.build(
        name=name,
        label=label,
        required=required,
        parser=parse_decimal,
        serializer=serialize_decimal,
        deserializer=deserialize_decimal,
        validator=validator,
    )


def bool_field(
    name: str,
    label: str,
    *,
    required: bool = False,
    validator=None,
) -> FieldSpec[ObjectT, bool]:
    return FieldSpec.build(
        name=name,
        label=label,
        required=required,
        parser=parse_bool,
        validator=validator,
    )


def date_field(
    name: str,
    label: str,
    *,
    required: bool = False,
    validator=None,
) -> FieldSpec[ObjectT, date]:
    return FieldSpec.build(
        name=name,
        label=label,
        required=required,
        parser=parse_date_iso,
        serializer=serialize_date,
        deserializer=deserialize_date,
        validator=validator,
    )


def datetime_field(
    name: str,
    label: str,
    *,
    required: bool = False,
    validator=None,
) -> FieldSpec[ObjectT, datetime]:
    return FieldSpec.build(
        name=name,
        label=label,
        required=required,
        parser=parse_datetime_iso,
        serializer=serialize_datetime,
        deserializer=deserialize_datetime,
        validator=validator,
    )


def enum_field(
    name: str,
    label: str,
    enum_cls: type[EnumT],
    *,
    required: bool = False,
    aliases: dict[str, EnumT] | None = None,
    canonical_pairs: Iterable[tuple[str, EnumT]] | None = None,
    validator=None,
) -> FieldSpec[ObjectT, EnumT]:
    canonical_pairs = canonical_pairs or [(str(member.value), member) for member in enum_cls]
    lookup = build_enum_alias_lookup(
        canonical_pairs=canonical_pairs,
        aliases=aliases,
    )

    return FieldSpec.build(
        name=name,
        label=label,
        required=required,
        parser=make_enum_parser(
            lookup,
            field_label=label,
        ),
        formatter=lambda v: v.value,
        serializer=serialize_enum,
        deserializer=make_enum_deserializer(enum_cls),
        validator=validator,
    )