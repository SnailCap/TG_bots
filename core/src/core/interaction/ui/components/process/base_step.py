from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from telegram import InlineKeyboardMarkup

from core.interaction.contracts.input_reactive import InputReactive
from core.interaction.input.user_input import UserInput
from core.interaction.ui.builders.keyboard_builder import KeyboardBuilder
from core.interaction.ui.components.process.effects import GoNext, GoPrev, StepResult
from core.interaction.ui.components import UiComponent


class Step(UiComponent, InputReactive):
    """
    Stateless Step.

    - Text variables and keyboard layout overrides are stored in the active process payload.
    - Effective keyboard layout:
        1) payload override ("keyboard_layout") if present and not None
        2) default_keyboard_layout provided at construction time (usually from config)
    """

    _PAYLOAD_TEXT_VARS = "text_variables"
    _PAYLOAD_KB_LAYOUT = "keyboard_layout"

    def __init__(
        self,
        text_template: str,
        inline_keyboard_template: Optional[InlineKeyboardMarkup] = None,
        *,
        keyboard_builder: Optional[KeyboardBuilder] = None,
        html_escape_variables: bool = False,
        default_keyboard_layout: Optional[Sequence[Sequence[Any]]] = None,
    ) -> None:
        super().__init__(
            text_template,
            inline_keyboard_template,
            keyboard_builder=keyboard_builder,
            html_escape_variables=html_escape_variables,
        )
        self._default_keyboard_layout = default_keyboard_layout

    async def render(self, user_input: UserInput, with_send: bool = False) -> None:
        await self._on_start(user_input)
        await super().render(user_input, with_send=with_send)

    async def _on_start(self, user_input: UserInput) -> None:
        # hook for subclasses (no-op by default)
        return

    async def handle_input(self, user_input: UserInput) -> StepResult:
        """Dispatch input to message/callback handlers and return a StepResult.

        Variant A: Steps do NOT transition via InteractionState meta.
        Instead, they return a directive (GoNext/GoPrev) or effects.
        """
        if user_input.is_callback:
            return await self.handle_callback(user_input)
        if user_input.is_message:
            return await self.handle_message(user_input)
        return None


    async def handle_message(self, user_input: UserInput) -> StepResult:
        # Default behavior: no state changes, coordinator will re-render the current step.
        return None

    async def handle_callback(self, user_input: UserInput) -> StepResult:
        # Default behavior: no state changes, coordinator will re-render the current step.
        return None

    async def is_input_valid(self, user_input: UserInput) -> bool:
        return True

    # --- navigation helpers ---
    @staticmethod
    def go_next() -> GoNext:
        return GoNext()

    @staticmethod
    def go_prev() -> GoPrev:
        return GoPrev()

    # --- state helpers ---
    def _active_proc(self, user_input: UserInput) -> Optional[str]:
        if not user_input.state.has_active_process():
            return None
        try:
            return user_input.state.get_active_process()
        except RuntimeError:
            return None

    def _payload(self, user_input: UserInput) -> dict:
        name = self._active_proc(user_input)
        return user_input.state.get_process_payload(name) if name else {}

    def _patch_payload(self, user_input: UserInput, **kwargs: Any) -> None:
        name = self._active_proc(user_input)
        if name:
            user_input.state.update_process_payload(name, **kwargs)

    # --- UiComponent hooks: where to store keyboard layout (optional runtime override) ---
    def _get_keyboard_layout_storage(self, user_input: UserInput) -> Any:
        return self._payload(user_input).get(self._PAYLOAD_KB_LAYOUT)

    def _set_keyboard_layout_storage(self, user_input: UserInput, value: Any) -> None:
        self._patch_payload(user_input, **{self._PAYLOAD_KB_LAYOUT: value})

    # --- layout ---
    def _get_keyboard_layout_effective(
        self, user_input: UserInput
    ) -> Optional[Sequence[Sequence[Any]]]:
        stored = self._get_keyboard_layout_storage(user_input)
        return stored if stored is not None else self._default_keyboard_layout

    # --- contexts ---
    async def _build_text_context(self, user_input: UserInput) -> Dict[str, Any]:
        return dict(self._payload(user_input).get(self._PAYLOAD_TEXT_VARS, {}) or {})

    async def _build_keyboard_context(self, user_input: UserInput) -> Dict[str, Any]:
        layout = self._get_keyboard_layout_effective(user_input)
        return {"layout": layout} if layout is not None else {}