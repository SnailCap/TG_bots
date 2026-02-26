# base_process.py
from __future__ import annotations

from abc import ABC
from typing import List

from core.src.interaction.input.user_input import UserInput
from core.src.interaction.ui.components.process.effects import (
    ProcessEffect,
    RenderStep,
    FinishProcess,
    CancelProcess,
)


class Process(ABC):
    """
    Process base class.

    LoD improvements:
    - Do not parse callback_data here.
      Use UserInput intent-level helpers: is_proc_next / is_proc_prev.
    - Minimize deep knowledge of state structure by using InteractionState façade.
    """

    step_names: list[str] = []

    # === internal ===

    @classmethod
    def _get_registered_key(cls) -> str:
        key = getattr(cls, "__ui_key__", None)
        if not key:
            raise RuntimeError(f"{cls.__name__} is not registered with @process('key')")
        return key

    def _key(self) -> str:
        return self._get_registered_key()

    # === lifecycle ===

    async def start(self, user_input: UserInput) -> List[ProcessEffect]: # NOSONAR
        key = self._key()
        st = user_input.state

        st.set_active_process(key)
        st.set_step_index(key, 0)

        # Always render the first step when the process starts.
        return [self._render_current_effect(user_input)]

    async def handle_input(self, user_input: UserInput) -> List[ProcessEffect]:
        # Prefer intent-level flags over callback parsing here (LoD).
        if user_input.is_proc_next:
            return await self.go_to_next_step(user_input)

        if user_input.is_proc_prev:
            return await self.go_to_previous_step(user_input)

        return []

    async def go_to_next_step(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        st = user_input.state

        if self._is_last_step_index(user_input):
            return await self.finish(user_input)

        idx = self._get_current_step_index(user_input)
        st.set_step_index(key, idx + 1)

        # After changing step index, explicitly render the new current step.
        return [self._render_current_effect(user_input)]

    async def go_to_previous_step(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        st = user_input.state

        idx = self._get_current_step_index(user_input)
        if idx <= 0:
            return await self.cancel(user_input)

        st.set_step_index(key, idx - 1)

        # After changing step index, explicitly render the new current step.
        return [self._render_current_effect(user_input)]

    async def finish(self, user_input: UserInput) -> List[ProcessEffect]: # NOSONAR
        key = self._key()
        st = user_input.state

        self._clear_state(user_input)
        st.set_finished_process(key)

        return [FinishProcess(key)]

    async def cancel(self, user_input: UserInput) -> List[ProcessEffect]: # NOSONAR
        key = self._key()
        st = user_input.state

        self._clear_state(user_input)
        st.set_canceled_process(key)

        return [CancelProcess(key)]

    # === helpers ===

    def _render_current_effect(self, user_input: UserInput) -> RenderStep:
        key = self._key()
        idx = self._get_current_step_index(user_input)

        if idx < 0 or idx >= len(self.step_names):
            raise IndexError(f"Step index out of range: {idx} for process '{key}'")

        return RenderStep(step_name=self.step_names[idx], with_send=False)

    def _is_last_step_index(self, user_input: UserInput) -> bool:
        return self._get_current_step_index(user_input) >= (len(self.step_names) - 1)

    def _get_current_step_index(self, user_input: UserInput) -> int:
        return user_input.state.get_step_index(self._key(), 0)

    def _clear_state(self, user_input: UserInput) -> None:
        key = self._key()
        st = user_input.state

        if st.has_active_process() and st.get_active_process() == key:
            st.clear_active_process()

        st.clear_process_state(key)