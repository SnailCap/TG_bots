from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class InputValidationResult:
    accepted: bool
    value: Any = None
    error: str | None = None


class InputValidator:
    def validate(self, raw: str | None, spec: Mapping[str, Any]) -> InputValidationResult:
        required = bool(spec.get("required", True))
        value = (raw or "").strip()
        if not value:
            if required:
                return self._reject(spec, "Value is required.")
            return InputValidationResult(True, None)

        expected = str(
            spec.get("input_type", spec.get("expected_type", spec.get("type", "string")))
        ).casefold()
        try:
            parsed = self._parse(value, expected)
        except ValueError as exc:
            return self._reject(spec, str(exc))

        regex = spec.get("regex")
        if regex and re.fullmatch(str(regex), value) is None:
            return self._reject(spec, "Value has an invalid format.")

        minimum = spec.get("min_value", spec.get("min", spec.get("minimum")))
        maximum = spec.get("max_value", spec.get("max", spec.get("maximum")))
        length_min = spec.get("min_length")
        length_max = spec.get("max_length")

        if length_min is not None and len(value) < int(length_min):
            return self._reject(spec, f"Minimum length is {length_min}.")
        if length_max is not None and len(value) > int(length_max):
            return self._reject(spec, f"Maximum length is {length_max}.")

        if minimum is not None and self._comparable(parsed) < self._comparable(minimum):
            return self._reject(spec, f"Minimum value is {minimum}.")
        if maximum is not None and self._comparable(parsed) > self._comparable(maximum):
            return self._reject(spec, f"Maximum value is {maximum}.")

        return InputValidationResult(True, parsed)

    @staticmethod
    def _parse(raw: str, expected: str) -> Any:
        if expected in {"string", "str", "text"}:
            return raw
        if expected in {"integer", "int"}:
            try:
                return int(raw)
            except ValueError as exc:
                raise ValueError("Expected an integer.") from exc
        if expected in {"number", "decimal", "float"}:
            try:
                return float(Decimal(raw.replace(",", ".")))
            except InvalidOperation as exc:
                raise ValueError("Expected a number.") from exc
        if expected in {"boolean", "bool"}:
            normalized = raw.casefold()
            if normalized in {"true", "1", "yes", "y", "on", "да", "д"}:
                return True
            if normalized in {"false", "0", "no", "n", "off", "нет", "н"}:
                return False
            raise ValueError("Expected a boolean value.")
        raise ValueError(f"Unsupported input type '{expected}'.")

    @staticmethod
    def _comparable(value: Any) -> Any:
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))
        return value

    @staticmethod
    def _reject(spec: Mapping[str, Any], fallback: str) -> InputValidationResult:
        return InputValidationResult(
            False,
            error=str(spec.get("error_message") or fallback),
        )
