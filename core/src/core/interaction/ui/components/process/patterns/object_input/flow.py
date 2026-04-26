from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ObjectInputFlowSpec:
    start_step: str
    linear_step_names: list[str]
    next_after_input: str | None
    next_after_edit: str | None