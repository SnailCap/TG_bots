from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Generic, Sequence, TypeVar

from core.interaction.input import FieldSpec, ObjectSchema
from core.interaction.input.scenarios import BulkTextInputSpec, BulkTextScenario

from .base import ObjectInputProcess
from .constants import InputFlowMode

ObjectT = TypeVar("ObjectT")


class SimpleObjectProcess(ObjectInputProcess[ObjectT]):
    model: type[ObjectT]
    fields: Sequence[FieldSpec[ObjectT, object]]
    flow_mode_value: InputFlowMode = InputFlowMode.INPUT_CONFIRM
    positional_fields: Sequence[str] = ()
    aliases: dict[str, str] = {}

    def schema(self) -> ObjectSchema[ObjectT]:
        return ObjectSchema(
            fields=tuple(self.fields),
            object_factory=self.model,
        )

    @cached_property
    def bulk_text_spec(self) -> BulkTextInputSpec:
        return BulkTextInputSpec(
            positional_fields=tuple(self.positional_fields),
            aliases=dict(self.aliases),
        )

    def build_scenario(self) -> BulkTextScenario[ObjectT]:
        return BulkTextScenario(
            schema=self.schema(),
            spec=self.bulk_text_spec,
        )

    def flow_mode(self) -> InputFlowMode:
        return self.flow_mode_value

    @abstractmethod
    async def submit_object(self, user_input, obj: ObjectT) -> None:
        ...