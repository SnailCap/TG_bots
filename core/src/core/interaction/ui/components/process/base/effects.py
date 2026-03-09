from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Union


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
# Step-level directives
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


@dataclass(frozen=True, slots=True)
class Finish:
    """Step requests graceful completion of the active process."""
    pass


@dataclass(frozen=True, slots=True)
class Cancel:
    """Step requests graceful cancellation of the active process."""
    pass


StepDirective = Union[GoNext, GoPrev, GoToStep, Finish, Cancel]
StepResult = Union[None, StepDirective, ProcessEffect, Sequence[ProcessEffect]]