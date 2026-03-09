from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from .field_spec import FieldSpec

DraftT = TypeVar("DraftT")


@dataclass(frozen=True, slots=True)
class DraftSchema(Generic[DraftT]):
    """
    Immutable schema for draft creation.
    """
    fields: tuple[FieldSpec[DraftT, object], ...]
    _fields_by_name: dict[str, FieldSpec[DraftT, object]] = field(init=False, repr=False)
    _alias_to_name: dict[str, str] = field(init=False, repr=False)
    _positional_fields: tuple[FieldSpec[DraftT, object], ...] = field(init=False, repr=False)
    _confirm_fields: tuple[FieldSpec[DraftT, object], ...] = field(init=False, repr=False)
    _required_fields: tuple[FieldSpec[DraftT, object], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        fields_by_name: dict[str, FieldSpec[DraftT, object]] = {}
        alias_to_name: dict[str, str] = {}
        positional_fields: list[FieldSpec[DraftT, object]] = []
        confirm_fields: list[FieldSpec[DraftT, object]] = []
        required_fields: list[FieldSpec[DraftT, object]] = []

        for field_spec in self.fields:
            if field_spec.name in fields_by_name:
                raise ValueError(f"Duplicate field name: '{field_spec.name}'")

            fields_by_name[field_spec.name] = field_spec
            alias_to_name[field_spec.name.lower()] = field_spec.name

            for alias in field_spec.aliases:
                alias_key = alias.lower()
                if alias_key in alias_to_name:
                    raise ValueError(f"Duplicate alias: '{alias}'")
                alias_to_name[alias_key] = field_spec.name

            if field_spec.positional:
                positional_fields.append(field_spec)
            if field_spec.include_in_confirm:
                confirm_fields.append(field_spec)
            if field_spec.required:
                required_fields.append(field_spec)

        object.__setattr__(self, "_fields_by_name", fields_by_name)
        object.__setattr__(self, "_alias_to_name", alias_to_name)
        object.__setattr__(self, "_positional_fields", tuple(positional_fields))
        object.__setattr__(self, "_confirm_fields", tuple(confirm_fields))
        object.__setattr__(self, "_required_fields", tuple(required_fields))

    @property
    def fields_by_name(self) -> dict[str, FieldSpec[DraftT, object]]:
        return self._fields_by_name

    @property
    def alias_to_name(self) -> dict[str, str]:
        return self._alias_to_name

    @property
    def positional_fields(self) -> tuple[FieldSpec[DraftT, object], ...]:
        return self._positional_fields

    @property
    def confirm_fields(self) -> tuple[FieldSpec[DraftT, object], ...]:
        return self._confirm_fields

    @property
    def required_fields(self) -> tuple[FieldSpec[DraftT, object], ...]:
        return self._required_fields

    def get_field(self, name: str) -> FieldSpec[DraftT, object]:
        try:
            return self._fields_by_name[name]
        except KeyError as e:
            raise KeyError(
                f"Unknown field '{name}'. Known fields: {list(self._fields_by_name.keys())}"
            ) from e

    def resolve_field_name(self, alias_or_name: str) -> str | None:
        return self._alias_to_name.get(alias_or_name.strip().lower())