from __future__ import annotations

from abc import ABC
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.interaction.input.user_input import UserInput
from .effects import (
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

    async def start(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        state.set_active_process(key)

        if not self.step_names:
            raise RuntimeError(f"Process '{key}' has no step_names.")

        state.set_step_key(key, self.step_names[0])

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
        state = user_input.state

        idx = self._get_current_step_index(user_input)
        if idx >= (len(self.step_names) - 1):
            return await self.finish(user_input)

        new_idx = idx + 1
        state.set_step_key(key, self.step_names[new_idx])

        return [self._render_current_effect(user_input)]

    async def go_to_previous_step(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        idx = self._get_current_step_index(user_input)
        if idx <= 0:
            return await self.cancel(user_input)

        new_idx = idx - 1
        state.set_step_key(key, self.step_names[new_idx])

        return [self._render_current_effect(user_input)]

    def go_to_step(self, user_input: UserInput, step_name: str) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        # validate
        if step_name not in self.step_names:
            raise KeyError(
                f"Unknown step_name '{step_name}' for process '{self._get_registered_key()}'. "
                f"Known: {self.step_names}"
            )

        state.set_step_key(key, step_name)
        return [self._render_current_effect(user_input)]

    async def finish(self, user_input: UserInput) -> List[ProcessEffect]:  # NOSONAR
        key = self._key()
        state = user_input.state

        self._clear_state(user_input)
        state.set_finished_process(key)

        return [FinishProcess(key)]

    async def cancel(self, user_input: UserInput) -> List[ProcessEffect]:  # NOSONAR
        key = self._key()
        state = user_input.state

        self._clear_state(user_input)
        state.set_canceled_process(key)

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
        key = self._key()
        state = user_input.state

        step_key = state.get_step_key(key)
        if step_key is None:
            # если по какой-то причине пусто — считаем, что это старт
            state.set_step_key(key, self.step_names[0])
            return 0

        if step_key not in self.step_names:
            raise KeyError(
                f"Unknown step_key '{step_key}' for process '{key}'. "
                f"Known: {self.step_names}"
            )

        return self.step_names.index(step_key)

    def _clear_state(self, user_input: UserInput) -> None:
        key = self._key()
        state = user_input.state

        if state.has_active_process() and state.get_active_process() == key:
            state.clear_active_process()

        state.clear_process_state(key)

    def _index_of_step_name(self, step_name: str) -> int:
        try:
            return self.step_names.index(step_name)
        except ValueError as e:
            raise KeyError(
                f"Unknown step_name '{step_name}' for process '{self._get_registered_key()}'. "
                f"Known: {self.step_names}"
            ) from e
