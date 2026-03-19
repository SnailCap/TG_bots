from __future__ import annotations

from typing import Generic, TypeVar, TYPE_CHECKING

from core.interaction.input import InputCodec

from .constants import ERRORS_KEY, OBJECT_DATA_KEY

if TYPE_CHECKING:
    from core.interaction.runtime.user_input import UserInput


ObjectT = TypeVar("ObjectT")


class ObjectInputPayloadStore(Generic[ObjectT]):
    def __init__(self, *, codec: InputCodec[ObjectT]) -> None:
        self._codec = codec

    def load_object(self, user_input: UserInput) -> ObjectT:
        payload = self._get_payload(user_input)
        return self._codec.load(payload.get(OBJECT_DATA_KEY))

    def save_object(self, user_input: UserInput, obj: ObjectT) -> None:
        self._patch_payload(
            user_input,
            **{OBJECT_DATA_KEY: self._codec.dump(obj)},
        )

    def get_errors(self, user_input: UserInput) -> list[str]:
        payload = self._get_payload(user_input)
        return list(payload.get(ERRORS_KEY, []) or [])

    def set_errors(self, user_input: UserInput, errors: list[str]) -> None:
        self._patch_payload(user_input, **{ERRORS_KEY: list(errors)})

    def clear_errors(self, user_input: UserInput) -> None:
        self.set_errors(user_input, [])

    @staticmethod
    def _get_payload(user_input: UserInput) -> dict:
        proc_key = user_input.state.get_active_process()
        return user_input.state.get_process_payload(proc_key)

    @staticmethod
    def _patch_payload(user_input: UserInput, **kwargs: object) -> None:
        proc_key = user_input.state.get_active_process()
        user_input.state.update_process_payload(proc_key, **kwargs)