from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar, TYPE_CHECKING

from core.interaction.ui.components.process.base.base_process import Process

from .codec import DraftCodec
from .constants import DEFAULT_CALLBACK_CONFIRM, DEFAULT_CALLBACK_EDIT
from .parser import DraftTextParser
from .payload import DraftPayloadStore
from .presenter import DraftPresenter
from .schema import DraftSchema
from .validator import DraftValidator

if TYPE_CHECKING:
    from core.interaction.input.user_input import UserInput

DraftT = TypeVar("DraftT")


@dataclass(frozen=True, slots=True)
class ConfirmStepCallbacks:
    edit: str = DEFAULT_CALLBACK_EDIT
    confirm: str = DEFAULT_CALLBACK_CONFIRM


class DraftCreateProcess(Process, ABC, Generic[DraftT]):
    """
    Reusable schema-driven create flow:

    collect -> edit -> confirm -> submit
    """

    collect_step_name: str
    edit_step_name: str
    confirm_step_name: str

    @classmethod
    @abstractmethod
    def schema(cls) -> DraftSchema[DraftT]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def draft_factory(cls) -> Callable[..., DraftT]:
        raise NotImplementedError

    def parser(self) -> DraftTextParser[DraftT]:
        return DraftTextParser(
            schema=self.schema(),
            draft_factory=self.draft_factory(),
        )

    def codec(self) -> DraftCodec[DraftT]:
        return DraftCodec(
            schema=self.schema(),
            draft_factory=self.draft_factory(),
        )

    def payload_store(self) -> DraftPayloadStore[DraftT]:
        return DraftPayloadStore(codec=self.codec())

    def presenter(self) -> DraftPresenter[DraftT]:
        return DraftPresenter(schema=self.schema())

    def validator(self) -> DraftValidator[DraftT]:
        return DraftValidator(schema=self.schema())

    def confirm_callbacks(self) -> ConfirmStepCallbacks:
        return ConfirmStepCallbacks()

    @property
    def step_names(self) -> list[str]:
        return [
            self.collect_step_name,
            self.edit_step_name,
            self.confirm_step_name,
        ]

    def validate_draft(self, user_input: UserInput, draft: DraftT) -> list[str]:
        """
        Domain hook.
        Core validation is applied automatically before this hook.
        """
        return []

    @abstractmethod
    async def submit_draft(self, user_input: UserInput, draft: DraftT) -> None:
        raise NotImplementedError

    def on_submit_error(
        self,
        user_input: UserInput,
        *,
        draft: DraftT,
        error: Exception,
    ) -> list[str]:
        return [str(error)]