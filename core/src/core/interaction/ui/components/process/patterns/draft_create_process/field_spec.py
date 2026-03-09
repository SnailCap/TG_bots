from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, Iterable, TypeVar

DraftT = TypeVar("DraftT")
ValueT = TypeVar("ValueT")

ParseFn = Callable[[str], ValueT]
FormatFn = Callable[[ValueT], str]
SerializeFn = Callable[[ValueT], Any]
DeserializeFn = Callable[[Any], ValueT]
ValidateFn = Callable[[DraftT, ValueT | None], list[str]]


@dataclass(frozen=True, slots=True)
class FieldSpec(Generic[DraftT, ValueT]):
    """
    Declarative field definition for schema-driven draft creation.
    """
    name: str
    label: str

    aliases: tuple[str, ...] = ()
    required: bool = False
    positional: bool = True
    include_in_confirm: bool = True

    parser: ParseFn[ValueT] | None = None
    formatter: FormatFn[ValueT] | None = None
    serializer: SerializeFn[ValueT] | None = None
    deserializer: DeserializeFn[ValueT] | None = None
    validator: ValidateFn[DraftT, ValueT] | None = None

    @classmethod
    def build(
        cls,
        *,
        name: str,
        label: str,
        aliases: Iterable[str] = (),
        required: bool = False,
        positional: bool = True,
        include_in_confirm: bool = True,
        parser: ParseFn[ValueT] | None = None,
        formatter: FormatFn[ValueT] | None = None,
        serializer: SerializeFn[ValueT] | None = None,
        deserializer: DeserializeFn[ValueT] | None = None,
        validator: ValidateFn[DraftT, ValueT] | None = None,
    ) -> "FieldSpec[DraftT, ValueT]":
        return cls(
            name=name,
            label=label,
            aliases=tuple(aliases),
            required=required,
            positional=positional,
            include_in_confirm=include_in_confirm,
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