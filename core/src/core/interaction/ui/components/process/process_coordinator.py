from __future__ import annotations

from dataclasses import dataclass
from typing import List, Type, cast

from core.interaction.contracts.ui_builder import UiBuilder
from core.interaction.input.user_input import UserInput
from core.interaction.ui.binding import get_default_registry
from core.interaction.ui.components.process import Process
from core.interaction.ui.components.process.effects import (
    ProcessEffect,
    RenderStep,
    FinishProcess,
    CancelProcess,
    GoNext,
    GoPrev,
    StepResult,
)


class UnknownProcessKey(RuntimeError):
    pass


@dataclass(slots=True)
class ProcessCoordinator:
    ui: UiBuilder

    async def handle(self, user_input: UserInput) -> bool:
        proc_key = user_input.state.get_active_process()
        if not proc_key:
            return False

        proc = self._resolve_process(proc_key)

        idx = user_input.state.get_step_index(proc_key, 0)
        if idx < 0 or idx >= len(proc.step_names):
            raise IndexError(f"Step index out of range: {idx} for process '{proc_key}'")

        step_name = proc.step_names[idx]
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

        if isinstance(result, (RenderStep, FinishProcess, CancelProcess)):
            return [result]

        return list(result)


    def _resolve_process(self, key: str) -> Process:
        registry = get_default_registry()
        cls = registry.get("process", key)

        if cls is None:
            raise UnknownProcessKey(f"Unknown process key: '{key}'")

        proc_cls = cast(Type[Process], cls)
        return proc_cls()

    async def _apply_effects(
            self,
            user_input: UserInput,
            effects: List[ProcessEffect],
    ) -> bool:
        ended = False

        for eff in effects:
            if isinstance(eff, RenderStep):
                step = self.ui.build_step(eff.step_name)
                await step.render(user_input, with_send=eff.with_send)

            elif isinstance(eff, (FinishProcess, CancelProcess)):
                ended = True

        return ended

    async def apply_effects(
            self,
            user_input: UserInput,
            effects: list[ProcessEffect],
    ) -> bool:
        return await self._apply_effects(user_input, effects)