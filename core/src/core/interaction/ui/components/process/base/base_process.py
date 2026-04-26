from __future__ import annotations

from abc import ABC
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from core.interaction.runtime.context.user_input import UserInput

from .effects import (
    CancelProcess,
    FinishProcess,
    ProcessEffect,
    RenderStep,
)


class Process(ABC):
    """
    step_names:
        Линейный основной flow процесса.
        Используется только для next/prev.

    allowed_step_names:
        Все допустимые шаги процесса, включая branch / auxiliary steps.
        Используется для явных переходов go_to_step() и для резолва активного шага.
    """

    step_names: list[str] = []

    @classmethod
    def _get_registered_key(cls) -> str:
        key = getattr(cls, "__ui_key__", None)
        if not key:
            raise RuntimeError(f"{cls.__name__} is not registered with @process('key')")
        return key

    def _key(self) -> str:
        return self._get_registered_key()

    @property
    def allowed_step_names(self) -> list[str]:
        return self.step_names

    async def start(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        state.set_active_process(key)

        if not self.step_names:
            raise RuntimeError(f"Process '{key}' has no step_names.")

        state.set_step_key(key, self.step_names[0])
        return [self._render_current_effect(user_input)]

    async def handle_input(self, user_input: UserInput) -> List[ProcessEffect]:
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

        state.set_step_key(key, self.step_names[idx + 1])
        return [self._render_current_effect(user_input)]

    async def go_to_previous_step(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        idx = self._get_current_step_index(user_input)
        if idx <= 0:
            return await self.cancel(user_input)

        state.set_step_key(key, self.step_names[idx - 1])
        return [self._render_current_effect(user_input)]

    def go_to_step(self, user_input: UserInput, step_name: str) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        if step_name not in self.allowed_step_names:
            raise KeyError(
                f"Unknown step_name '{step_name}' for process '{self._get_registered_key()}'. "
                f"Allowed: {self.allowed_step_names}"
            )

        state.set_step_key(key, step_name)
        return [self._render_current_effect(user_input)]

    async def finish(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        self._clear_state(user_input)
        state.set_finished_process(key)

        return [FinishProcess(key)]

    async def cancel(self, user_input: UserInput) -> List[ProcessEffect]:
        key = self._key()
        state = user_input.state

        self._clear_state(user_input)
        state.set_canceled_process(key)

        return [CancelProcess(key)]

    def _render_current_effect(self, user_input: UserInput) -> RenderStep:
        key = self._key()
        state = user_input.state

        step_key = state.get_step_key(key)
        if step_key is None:
            if not self.step_names:
                raise RuntimeError(f"Process '{key}' has no step_names.")
            step_key = self.step_names[0]
            state.set_step_key(key, step_key)

        if step_key not in self.allowed_step_names:
            raise KeyError(
                f"Unknown step_key '{step_key}' for process '{key}'. "
                f"Allowed: {self.allowed_step_names}"
            )

        return RenderStep(step_name=step_key, with_send=False)

    def _get_current_step_index(self, user_input: UserInput) -> int:
        key = self._key()
        state = user_input.state

        step_key = state.get_step_key(key)
        if step_key is None:
            if not self.step_names:
                raise RuntimeError(f"Process '{key}' has no step_names.")
            state.set_step_key(key, self.step_names[0])
            return 0

        if step_key not in self.step_names:
            raise KeyError(
                f"Step '{step_key}' is not in linear flow of process '{key}'. "
                f"Linear flow: {self.step_names}"
            )

        return self.step_names.index(step_key)

    def _clear_state(self, user_input: UserInput) -> None:
        key = self._key()
        state = user_input.state

        if state.has_active_process() and state.get_active_process() == key:
            state.clear_active_process()

        state.clear_process_state(key)