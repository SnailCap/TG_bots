from __future__ import annotations

from typing import Generic, TypeVar, TYPE_CHECKING

from .codec import DraftCodec
from .constants import DRAFT_KEY, ERRORS_KEY

if TYPE_CHECKING:
    from core.interaction.input.user_input import UserInput

DraftT = TypeVar("DraftT")


class DraftPayloadStore(Generic[DraftT]):
    def __init__(self, *, codec: DraftCodec[DraftT]) -> None:
        self._codec = codec

    def load_draft(self, user_input: UserInput) -> DraftT:
        payload = self._get_payload(user_input)
        return self._codec.load(payload.get(DRAFT_KEY))

    def save_draft(self, user_input: UserInput, draft: DraftT) -> None:
        self._patch_payload(
            user_input,
            **{DRAFT_KEY: self._codec.dump(draft)},
        )

    def merge_with_saved(self, user_input: UserInput, patch: DraftT) -> DraftT:
        base = self.load_draft(user_input)
        return self._codec.merge(base=base, patch=patch)

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