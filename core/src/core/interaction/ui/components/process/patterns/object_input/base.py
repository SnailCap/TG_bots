from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Generic, TypeVar, TYPE_CHECKING

from core.interaction.input import InputCodec, InputValidator, ObjectSchema
from core.interaction.input.scenarios.base import InputScenario
from core.interaction.ui.components.process.base.base_process import Process

from .constants import DEFAULT_CALLBACK_CONFIRM, DEFAULT_CALLBACK_EDIT, InputFlowMode
from .flow import ObjectInputFlowSpec
from .payload import ObjectInputPayloadStore

if TYPE_CHECKING:
    from core.interaction.runtime.context.user_input import UserInput


ObjectT = TypeVar("ObjectT")


@dataclass(frozen=True, slots=True)
class ConfirmStepCallbacks:
    edit: str = DEFAULT_CALLBACK_EDIT
    confirm: str = DEFAULT_CALLBACK_CONFIRM


class ObjectInputProcess(Process, ABC, Generic[ObjectT]):
    input_step_name: str
    edit_step_name: str
    confirm_step_name: str

    @classmethod
    @abstractmethod
    def schema(cls) -> ObjectSchema[ObjectT]:
        raise NotImplementedError

    @abstractmethod
    def build_scenario(self) -> InputScenario[ObjectT, str]:
        raise NotImplementedError

    @cached_property
    def scenario(self) -> InputScenario[ObjectT, str]:
        return self.build_scenario()

    @cached_property
    def codec(self) -> InputCodec[ObjectT]:
        return InputCodec(schema=self.schema())

    @cached_property
    def validator(self) -> InputValidator[ObjectT]:
        return InputValidator(schema=self.schema())

    @cached_property
    def payload_store(self) -> ObjectInputPayloadStore[ObjectT]:
        return ObjectInputPayloadStore(codec=self.codec)

    def flow_mode(self) -> InputFlowMode:
        return InputFlowMode.INPUT_CONFIRM

    def confirm_callbacks(self) -> ConfirmStepCallbacks:
        return ConfirmStepCallbacks()

    @cached_property
    def flow(self) -> ObjectInputFlowSpec:
        mode = self.flow_mode()

        if mode == InputFlowMode.INPUT_ONLY:
            return ObjectInputFlowSpec(
                start_step=self.input_step_name,
                linear_step_names=[self.input_step_name],
                next_after_input=None,
                next_after_edit=None,
            )

        if mode == InputFlowMode.INPUT_CONFIRM:
            return ObjectInputFlowSpec(
                start_step=self.input_step_name,
                linear_step_names=[self.input_step_name, self.confirm_step_name],
                next_after_input=self.confirm_step_name,
                next_after_edit=self.confirm_step_name,
            )

        if mode == InputFlowMode.EDIT_ONLY:
            return ObjectInputFlowSpec(
                start_step=self.edit_step_name,
                linear_step_names=[self.edit_step_name],
                next_after_input=None,
                next_after_edit=None,
            )

        if mode == InputFlowMode.EDIT_CONFIRM:
            return ObjectInputFlowSpec(
                start_step=self.edit_step_name,
                linear_step_names=[self.edit_step_name, self.confirm_step_name],
                next_after_input=None,
                next_after_edit=self.confirm_step_name,
            )

        raise ValueError(f"Unsupported flow mode: {mode}")

    @property
    def step_names(self) -> list[str]:
        return self.flow.linear_step_names

    @property
    def allowed_step_names(self) -> list[str]:
        names: list[str] = []
        for step_name in (
            self.input_step_name,
            self.confirm_step_name,
            self.edit_step_name,
        ):
            if step_name and step_name not in names:
                names.append(step_name)
        return names

    def get_start_step_name(self) -> str:
        return self.flow.start_step

    def validate_object(self, user_input: UserInput, obj: ObjectT) -> list[str]:
        return []

    def confirm_validation_error_step_name(self) -> str:
        return self.edit_step_name

    @abstractmethod
    async def submit_object(self, user_input: UserInput, obj: ObjectT) -> None:
        raise NotImplementedError

    def on_submit_error(
        self,
        user_input: UserInput,
        *,
        obj: ObjectT,
        error: Exception,
    ) -> list[str]:
        return [str(error)]