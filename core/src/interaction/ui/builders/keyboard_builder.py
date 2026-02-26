from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from telegram import InlineKeyboardMarkup

from core.src.interaction.ui.builders.button_builder import ButtonBuilder, ButtonBuildError
from core.src.interaction.ui.keyboard.button_ref import ButtonRef  # ✅ новый импорт


class KeyboardBuildError(RuntimeError):
    """Base error for keyboard building."""


class InvalidKeyboardLayout(KeyboardBuildError):
    pass


class ButtonKeyNotFoundInLayout(KeyboardBuildError):
    pass


@dataclass(slots=True)
class KeyboardBuilder:
    button_builder: ButtonBuilder

    def build(self, layout: Sequence[Sequence[Any]]) -> InlineKeyboardMarkup:
        self._validate_layout(layout)

        keyboard_rows = []
        for row_idx, row in enumerate(layout):
            self._validate_row(row, row_idx)
            built_row = self._build_row(row, row_idx)
            if built_row:
                keyboard_rows.append(built_row)

        return InlineKeyboardMarkup(keyboard_rows)

    def build_optional(self, layout: Sequence[Sequence[Any]] | None) -> InlineKeyboardMarkup | None:
        return None if layout is None else self.build(layout)

    # ---------- helpers ----------
    def _validate_layout(self, layout: Any) -> None:
        if layout is None:
            raise InvalidKeyboardLayout("keyboard_layout is None (use build_optional if it's allowed)")
        if not self._is_sequence(layout):
            raise InvalidKeyboardLayout("keyboard_layout must be a sequence of rows")

    def _validate_row(self, row: Any, row_idx: int) -> None:
        if not self._is_sequence(row):
            raise InvalidKeyboardLayout(f"Row #{row_idx} must be a sequence of buttons")

    def _build_row(self, row: Sequence[Any], row_idx: int):
        built_row = []
        for col_idx, raw in enumerate(row):
            ref = self._normalize_button(raw, row_idx=row_idx, col_idx=col_idx)
            if ref is None:
                continue
            built_row.append(self._build_button_or_raise(ref, row_idx=row_idx, col_idx=col_idx))
        return built_row

    def _normalize_button(self, raw: Any, *, row_idx: int, col_idx: int) -> ButtonRef | None:
        """
        Accepts:
          - None -> skip
          - str -> treated as button key
          - ButtonRef -> rich reference (key + vars + visible)
        """
        if raw is None:
            return None

        if isinstance(raw, ButtonRef):
            return None if not raw.visible else raw

        if isinstance(raw, str):
            key = raw.strip()
            return ButtonRef(key=key) if key else None

        raise InvalidKeyboardLayout(
            f"Button must be a string key or ButtonRef. row={row_idx} col={col_idx} value={raw!r}"
        )

    def _build_button_or_raise(self, ref: ButtonRef, *, row_idx: int, col_idx: int):
        try:
            return self.button_builder.build(ref.key, vars=ref.vars)
        except ButtonBuildError as e:
            raise ButtonKeyNotFoundInLayout(
                f"Failed to build button '{ref.key}' referenced in keyboard_layout "
                f"(row={row_idx}, col={col_idx}). {e}"
            ) from e

    @staticmethod
    def _is_sequence(value: Any) -> bool:
        return isinstance(value, Sequence) and not isinstance(value, (str, bytes))