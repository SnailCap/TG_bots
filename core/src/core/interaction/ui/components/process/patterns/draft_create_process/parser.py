from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from .schema import DraftSchema

DraftT = TypeVar("DraftT")


@dataclass(frozen=True, slots=True)
class ParseResult(Generic[DraftT]):
    draft: DraftT
    errors: list[str]


class DraftTextParser(Generic[DraftT]):
    def __init__(
        self,
        *,
        schema: DraftSchema[DraftT],
        draft_factory: Callable[..., DraftT],
    ) -> None:
        self._schema = schema
        self._draft_factory = draft_factory

    def parse_initial(self, text: str) -> ParseResult[DraftT]:
        lines = self._normalized_lines(text)

        positional_values: list[str] = []
        keyword_values: dict[str, str] = {}
        errors: list[str] = []
        keyword_mode = False

        for line in lines:
            if ":" in line:
                keyword_mode = True
                key, value = self._split_pair(line)

                field_name = self._schema.resolve_field_name(key)
                if field_name is None:
                    errors.append(f"Unknown field: {key}")
                    continue

                keyword_values[field_name] = value
                continue

            if keyword_mode:
                continue

            positional_values.append(line)

        parsed: dict[str, object] = {}

        for index, raw_value in enumerate(positional_values):
            if index >= len(self._schema.positional_fields):
                errors.append(f"Too many positional lines: '{raw_value}'")
                continue

            field_spec = self._schema.positional_fields[index]
            try:
                parsed[field_spec.name] = field_spec.parse_value(raw_value)
            except Exception as e:
                errors.append(f"{field_spec.label}: {e}")

        for field_name, raw_value in keyword_values.items():
            field_spec = self._schema.get_field(field_name)
            try:
                parsed[field_spec.name] = field_spec.parse_value(raw_value)
            except Exception as e:
                errors.append(f"{field_spec.label}: {e}")

        draft = self._draft_factory(**parsed)
        return ParseResult(draft=draft, errors=errors)

    def parse_patch(self, text: str) -> ParseResult[DraftT]:
        lines = self._normalized_lines(text)
        parsed: dict[str, object] = {}
        errors: list[str] = []

        for line in lines:
            if ":" not in line:
                errors.append(f"Line must be in 'field: value' format: {line}")
                continue

            key, value = self._split_pair(line)

            field_name = self._schema.resolve_field_name(key)
            if field_name is None:
                errors.append(f"Unknown field: {key}")
                continue

            field_spec = self._schema.get_field(field_name)
            try:
                parsed[field_spec.name] = field_spec.parse_value(value)
            except Exception as e:
                errors.append(f"{field_spec.label}: {e}")

        draft = self._draft_factory(**parsed)
        return ParseResult(draft=draft, errors=errors)

    @staticmethod
    def _normalized_lines(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _split_pair(line: str) -> tuple[str, str]:
        key, value = line.split(":", 1)
        return key.strip(), value.strip()