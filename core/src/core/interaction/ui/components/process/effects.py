from __future__ import annotations

from dataclasses import dataclass
from typing import Union, Sequence


# -------------------------
# Process-level effects
# -------------------------

@dataclass(frozen=True, slots=True)
class RenderStep:
    step_name: str
    with_send: bool = False


@dataclass(frozen=True, slots=True)
class FinishProcess:
    name: str


@dataclass(frozen=True, slots=True)
class CancelProcess:
    name: str


ProcessEffect = Union[RenderStep, FinishProcess, CancelProcess]


# -------------------------
# Step-level directives (Variant A)
# -------------------------

@dataclass(frozen=True, slots=True)
class GoNext:
    """Step requests transition to the next step of the active process."""
    pass


@dataclass(frozen=True, slots=True)
class GoPrev:
    """Step requests transition to the previous step of the active process."""
    pass


@dataclass(frozen=True, slots=True)
class GoToStep:
    """Step requests transition to a specific step of the active process."""
    step_name: str


StepDirective = Union[GoNext, GoPrev, GoToStep]
StepResult = Union[None, StepDirective, ProcessEffect, Sequence[ProcessEffect]]
