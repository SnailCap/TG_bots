from __future__ import annotations

from dataclasses import dataclass
from typing import List, Type, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from core.interaction.runtime.user_input import UserInput

from core.interaction.ui.build import UiBuilder
from core.interaction.ui.binding import get_default_ui_registry
from .base_process import Process
from .effects import (
    Cancel,
    CancelProcess,
    Finish,
    FinishProcess,
    GoNext,
    GoPrev,
    GoToStep,
    ProcessEffect,
    RenderStep,
    StepResult,
)


class UnknownProcessKey(RuntimeError):
    pass


@dataclass(slots=True)
class ProcessCoordinator:
    ui: UiBuilder

    async def handle(self, user_input: UserInput) -> bool:
        if not user_input.state.has_active_process():
            return False

        proc_key = user_input.state.get_active_process()
        proc = self._resolve_process(proc_key)

        step_name = self._resolve_active_step_name(user_input, proc_key, proc)
        step = self.ui.build_step(step_name)

        if user_input.is_proc_next or user_input.is_proc_prev:
            effects = await proc.handle_input(user_input)
        else:
            step_result: StepResult = await step.handle_input(user_input)
            effects = await self._effects_from_step_result(user_input, proc, step_result)

        if not effects:
            effects = [RenderStep(step_name)]

        ended = await self._apply_effects(user_input, effects)
        return ended

    def _resolve_active_step_name(self, user_input: UserInput, proc_key: str, proc: Process) -> str:
        state = user_input.state

        step_key = state.get_step_key(proc_key)
        if step_key is None:
            if not proc.step_names:
                raise RuntimeError(f"Process '{proc_key}' has no step_names.")
            step_key = proc.step_names[0]
            state.set_step_key(proc_key, step_key)

        if step_key not in proc.step_names:
            raise KeyError(
                f"Unknown step_key '{step_key}' for process '{proc_key}'. "
                f"Known: {proc.step_names}"
            )

        return step_key

    async def _effects_from_step_result(
        self,
        user_input: UserInput,
        proc: Process,
        result: StepResult,
    ) -> List[ProcessEffect]:
        if result is None:
            return []

        if isinstance(result, GoNext):
            return await proc.go_to_next_step(user_input)

        if isinstance(result, GoPrev):
            return await proc.go_to_previous_step(user_input)

        if isinstance(result, GoToStep):
            return proc.go_to_step(user_input, result.step_name)

        if isinstance(result, Finish):
            return await proc.finish(user_input)

        if isinstance(result, Cancel):
            return await proc.cancel(user_input)

        if isinstance(result, (RenderStep, FinishProcess, CancelProcess)):
            return [result]

        return list(result)

    def _resolve_process(self, key: str) -> Process:
        registry = get_default_ui_registry()
        cls = registry.get("process", key)

        if cls is None:
            raise UnknownProcessKey(f"Unknown process key: '{key}'")

        proc_cls = cast(Type[Process], cls)
        return proc_cls()

    async def _apply_effects(self, user_input: UserInput, effects: List[ProcessEffect]) -> bool:
        ended = False

        for eff in effects:
            if isinstance(eff, RenderStep):
                step = self.ui.build_step(eff.step_name)
                await step.render(user_input, with_send=eff.with_send)

            elif isinstance(eff, (FinishProcess, CancelProcess)):
                ended = True

        return ended

    async def apply_effects(self, user_input: UserInput, effects: list[ProcessEffect]) -> bool:
        return await self._apply_effects(user_input, effects)