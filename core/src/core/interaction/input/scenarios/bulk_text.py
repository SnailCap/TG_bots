from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar, Generic

from core.interaction.input import InputParseResult, InputValues
from core.interaction.input.scenarios.base import InputScenario

ObjectT = TypeVar("ObjectT")

def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("ё", "е")


@dataclass(frozen=True, slots=True)
class BulkTextInputSpec:
    positional_fields: tuple[str, ...] = ()
    aliases: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_aliases = {
            _normalize_key(key): field_name
            for key, field_name in self.aliases.items()
        }
        object.__setattr__(self, "aliases", normalized_aliases)

    def resolve_field_name(self, raw_name: str) -> str | None:
        key = _normalize_key(raw_name)
        if key in self.aliases:
            return self.aliases[key]
        return raw_name.strip()


class BulkTextScenario(InputScenario[ObjectT, str], Generic[ObjectT]):
    def __init__(self, *, schema, spec: BulkTextInputSpec) -> None:
        super().__init__(schema=schema)
        self._spec = spec

    @property
    def spec(self) -> BulkTextInputSpec:
        return self._spec

    def parse(self, raw_input: str) -> InputParseResult:
        lines = self._normalized_lines(raw_input)

        positional_values: list[str] = []
        keyword_values: dict[str, str] = {}
        errors: list[str] = []
        keyword_mode = False

        for line in lines:
            if ":" in line:
                keyword_mode = True
                key, value = self._split_pair(line)

                field_name = self._resolve_field_name(key)
                if field_name is None:
                    errors.append(f"Unknown field: {key}")
                    continue

                keyword_values[field_name] = value
                continue

            if keyword_mode:
                errors.append(
                    f"Line without 'field: value' is not allowed after keyword mode started: {line}"
                )
                continue

            positional_values.append(line)

        parsed: dict[str, object] = {}

        for index, raw_value in enumerate(positional_values):
            if index >= len(self.spec.positional_fields):
                errors.append(f"Too many positional lines: '{raw_value}'")
                continue

            field_name = self.spec.positional_fields[index]

            if not self.schema.has_field(field_name):
                errors.append(f"Unknown positional field in spec: {field_name}")
                continue

            field_spec = self.schema.get_field(field_name)

            try:
                parsed[field_spec.name] = field_spec.parse_value(raw_value)
            except Exception as e:
                errors.append(f"{field_spec.label}: {e}")

        for field_name, raw_value in keyword_values.items():
            if not self.schema.has_field(field_name):
                errors.append(f"Unknown field: {field_name}")
                continue

            field_spec = self.schema.get_field(field_name)

            try:
                parsed[field_spec.name] = field_spec.parse_value(raw_value)
            except Exception as e:
                errors.append(f"{field_spec.label}: {e}")

        return InputParseResult(
            data=InputValues(values=parsed),
            errors=errors,
        )

    def _resolve_field_name(self, raw_name: str) -> str | None:
        resolved = self.spec.resolve_field_name(raw_name)
        if resolved is None:
            return None

        if not self.schema.has_field(resolved):
            return None

        return resolved

    @staticmethod
    def _normalized_lines(text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    @staticmethod
    def _split_pair(line: str) -> tuple[str, str]:
        key, value = line.split(":", 1)
        return key.strip(), value.strip()