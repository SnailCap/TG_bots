from __future__ import annotations

from typing import Generic, TypeVar

from .codec import DraftCodec
from .constants import DEFAULT_ERROR_TEXT_KEY
from .schema import DraftSchema

DraftT = TypeVar("DraftT")


class DraftPresenter(Generic[DraftT]):
    def __init__(self, *, schema: DraftSchema[DraftT]) -> None:
        self._schema = schema

    def build_text_variables(
        self,
        *,
        draft: DraftT,
        errors: list[str] | None = None,
        error_key: str = DEFAULT_ERROR_TEXT_KEY,
    ) -> dict[str, str]:
        raw = DraftCodec.as_mapping(draft)
        result: dict[str, str] = {}

        for field_spec in self._schema.confirm_fields:
            result[field_spec.name] = field_spec.format_value(raw.get(field_spec.name))

        result[error_key] = self.format_errors(errors or [])
        return result

    @staticmethod
    def format_errors(errors: list[str]) -> str:
        if not errors:
            return ""
        return "\n".join(f"• {error}" for error in errors)