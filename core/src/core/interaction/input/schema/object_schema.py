from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from .field_spec import FieldSpec
from .results import ObjectBuildResult

ObjectT = TypeVar("ObjectT")


@dataclass(frozen=True, slots=True)
class ObjectSchema(Generic[ObjectT]):
    fields: tuple[FieldSpec[ObjectT, object], ...]
    object_factory: Callable[..., ObjectT]

    _fields_by_name: dict[str, FieldSpec[ObjectT, object]] = field(init=False, repr=False)
    _required_fields: tuple[FieldSpec[ObjectT, object], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        fields_by_name: dict[str, FieldSpec[ObjectT, object]] = {}
        required_fields: list[FieldSpec[ObjectT, object]] = []

        for field_spec in self.fields:
            if field_spec.name in fields_by_name:
                raise ValueError(f"Duplicate field name: '{field_spec.name}'")

            fields_by_name[field_spec.name] = field_spec

            if field_spec.required:
                required_fields.append(field_spec)

        object.__setattr__(self, "_fields_by_name", fields_by_name)
        object.__setattr__(self, "_required_fields", tuple(required_fields))

    @property
    def fields_by_name(self) -> dict[str, FieldSpec[ObjectT, object]]:
        return self._fields_by_name

    @property
    def required_fields(self) -> tuple[FieldSpec[ObjectT, object], ...]:
        return self._required_fields

    def get_field(self, name: str) -> FieldSpec[ObjectT, object]:
        try:
            return self._fields_by_name[name]
        except KeyError as e:
            raise KeyError(
                f"Unknown field '{name}'. Known fields: {list(self._fields_by_name.keys())}"
            ) from e

    def has_field(self, name: str) -> bool:
        return name in self._fields_by_name

    def build_object(self, values: dict[str, Any]) -> ObjectBuildResult[ObjectT]:
        try:
            obj = self.object_factory(**values)
        except Exception as e:
            return ObjectBuildResult(obj=None, errors=[str(e)])

        return ObjectBuildResult(obj=obj, errors=[])