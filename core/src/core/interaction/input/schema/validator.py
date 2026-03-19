from __future__ import annotations

from typing import Generic, TypeVar

from .codec import InputCodec
from .object_schema import ObjectSchema

ObjectT = TypeVar("ObjectT")


class InputValidator(Generic[ObjectT]):
    """
    Object-level validation:
    - required fields from schema
    - field-level validators
    """

    def __init__(self, *, schema: ObjectSchema[ObjectT]) -> None:
        self._schema = schema

    def validate(self, obj: ObjectT) -> list[str]:
        raw = InputCodec.as_mapping(obj)
        errors: list[str] = []

        errors.extend(self._validate_required(raw))
        errors.extend(self._validate_fields(obj, raw))

        return errors

    def _validate_required(self, raw: dict[str, object]) -> list[str]:
        errors: list[str] = []

        for field_spec in self._schema.required_fields:
            value = raw.get(field_spec.name)
            if self._is_missing(value):
                errors.append(f"{field_spec.label}: required")

        return errors

    def _validate_fields(
        self,
        obj: ObjectT,
        raw: dict[str, object],
    ) -> list[str]:
        errors: list[str] = []

        for field_spec in self._schema.fields:
            if field_spec.validator is None:
                continue

            value = raw.get(field_spec.name)
            try:
                field_errors = field_spec.validator(obj, value)
            except Exception as e:
                errors.append(f"{field_spec.label}: {e}")
                continue

            if field_errors:
                errors.extend(field_errors)

        return errors

    @staticmethod
    def _is_missing(value: object) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        return False