from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from core.interaction.input.schema.object_schema import ObjectSchema
from core.interaction.input.schema.results import InputParseResult

ObjectT = TypeVar("ObjectT")
RawInputT = TypeVar("RawInputT")


class InputScenario(ABC, Generic[ObjectT, RawInputT]):
    """
    Scenario transforms some raw input into normalized field values.

    Examples of raw input:
    - str (bulk text, json text)
    - dict[str, str]
    - callback payload
    - (field_name, raw_value)

    Scenario does NOT:
    - persist data
    - know about Process/Step
    - own object validation rules
    """

    def __init__(self, *, schema: ObjectSchema[ObjectT]) -> None:
        self._schema = schema

    @property
    def schema(self) -> ObjectSchema[ObjectT]:
        return self._schema

    @abstractmethod
    def parse(self, raw_input: RawInputT) -> InputParseResult:
        raise NotImplementedError