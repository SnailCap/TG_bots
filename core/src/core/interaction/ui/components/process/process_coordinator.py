from __future__ import annotations

from dataclasses import dataclass
from typing import List, Type, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from core.interaction.input.user_input import UserInput
from ...build import UiBuilder
from ...binding import get_default_ui_registry
from .base_process import Process
from .effects import (
    ProcessEffect,
    RenderStep,
    FinishProcess,
    CancelProcess,
    GoNext,
    GoPrev,
    GoToStep,
    StepResult,
)


class UnknownProcessKey(RuntimeError):
    pass


@dataclass(slots=True)
class ProcessCoordinator:
    ui: UiBuilder

    async def handle(self, user_input: UserInput) -> bool:
        # Be robust: InteractionState.get_active_process() raises if not set.
        if not user_input.state.has_active_process():
            return False

        proc_key = user_input.state.get_active_process()
        proc = self._resolve_process(proc_key)

        step_name = self._resolve_active_step_name(user_input, proc_key, proc)
        step = self.ui.build_step(step_name)

        # Process-level navigation commands have priority (svc:prc:*).
        if user_input.is_proc_next or user_input.is_proc_prev:
            effects = await proc.handle_input(user_input)
        else:
            step_result: StepResult = await step.handle_input(user_input)
            effects = await self._effects_from_step_result(user_input, proc, step_result)

        # Default: re-render the current step if nobody produced effects.
        if not effects:
            effects = [RenderStep(step_name)]

        ended = await self._apply_effects(user_input, effects)
        return ended

    def _resolve_active_step_name(self, user_input: UserInput, proc_key: str, proc: Process) -> str:
        """
        Source of truth: step_key in state.

        Backward compatibility:
        - If step_key is missing, fallback to step_index and *persist* step_key.
        - If step_key is invalid, try to recover via step_index; otherwise raise.
        """
        state = user_input.state

        step_key = state.get_step_key(proc_key)
        if step_key is None:
            if not proc.step_names:
                raise RuntimeError(f"Process '{proc_key}' has no step_names.")
            step_key = proc.step_names[0]
            state.set_step_key(proc_key, step_key)

        if step_key not in proc.step_names:
            raise KeyError(...)
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

        if isinstance(result, (RenderStep, FinishProcess, CancelProcess)):
            return [result]

        # Sequence[ProcessEffect]
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
