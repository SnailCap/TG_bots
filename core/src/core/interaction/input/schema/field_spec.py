from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

ObjectT = TypeVar("ObjectT")
ValueT = TypeVar("ValueT")

ParseFn = Callable[[str], ValueT]
FormatFn = Callable[[ValueT], str]
SerializeFn = Callable[[ValueT], Any]
DeserializeFn = Callable[[Any], ValueT]
ValidateFn = Callable[[ObjectT, ValueT | None], list[str]]


@dataclass(frozen=True, slots=True)
class FieldSpec(Generic[ObjectT, ValueT]):
    """
    Pure object field definition.

    This class intentionally knows nothing about:
    - positional order
    - aliases
    - bulk text
    - JSON keys
    - confirm/presentation policies

    These concerns belong to input scenarios or presentation specs.
    """
    name: str
    label: str

    required: bool = False

    parser: ParseFn[ValueT] | None = None
    formatter: FormatFn[ValueT] | None = None
    serializer: SerializeFn[ValueT] | None = None
    deserializer: DeserializeFn[Any] | None = None
    validator: ValidateFn[ObjectT, ValueT] | None = None

    @classmethod
    def build(
        cls,
        *,
        name: str,
        label: str,
        required: bool = False,
        parser: ParseFn[ValueT] | None = None,
        formatter: FormatFn[ValueT] | None = None,
        serializer: SerializeFn[ValueT] | None = None,
        deserializer: DeserializeFn[Any] | None = None,
        validator: ValidateFn[ObjectT, ValueT] | None = None,
    ) -> "FieldSpec[ObjectT, ValueT]":
        return cls(
            name=name,
            label=label,
            required=required,
            parser=parser,
            formatter=formatter,
            serializer=serializer,
            deserializer=deserializer,
            validator=validator,
        )

    def parse_value(self, raw: str) -> Any:
        value = raw.strip()
        if self.parser is None:
            return value
        return self.parser(value)

    def format_value(self, value: Any) -> str:
        if value is None:
            return "—"
        if self.formatter is None:
            return str(value)
        return self.formatter(value)

    def dump_value(self, value: Any) -> Any:
        if value is None:
            return None
        if self.serializer is None:
            return value
        return self.serializer(value)

    def load_value(self, value: Any) -> Any:
        if value is None:
            return None
        if self.deserializer is None:
            return value
        return self.deserializer(value)