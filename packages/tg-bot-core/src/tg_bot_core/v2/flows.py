from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TYPE_CHECKING

from .events import InteractionEvent

if TYPE_CHECKING:
    from .app import FlowContext


class TransitionKind(StrEnum):
    GOTO = "goto"
    RENDER = "render"
    SEND = "send"
    FINISH = "finish"
    CANCEL = "cancel"
    FAIL = "fail"
    ENQUEUE = "enqueue"


@dataclass(frozen=True, slots=True)
class JobRequest:
    task: str
    payload: dict[str, Any] = field(default_factory=dict)
    delay_seconds: float = 0


@dataclass(frozen=True, slots=True)
class Transition:
    kind: TransitionKind
    state: str | None = None
    view: str | None = None
    text: str | None = None
    variables: Mapping[str, Any] = field(default_factory=dict)
    job: JobRequest | None = None
    error: str | None = None

    @classmethod
    def goto(cls, state: str, *, view: str | None = None, variables: Mapping[str, Any] | None = None) -> "Transition":
        return cls(TransitionKind.GOTO, state=state, view=view, variables=dict(variables or {}))

    @classmethod
    def render(cls, view: str, *, variables: Mapping[str, Any] | None = None) -> "Transition":
        return cls(TransitionKind.RENDER, view=view, variables=dict(variables or {}))

    @classmethod
    def send(cls, text: str, *, variables: Mapping[str, Any] | None = None) -> "Transition":
        return cls(TransitionKind.SEND, text=text, variables=dict(variables or {}))

    @classmethod
    def finish(cls, *, view: str | None = None, variables: Mapping[str, Any] | None = None) -> "Transition":
        return cls(TransitionKind.FINISH, view=view, variables=dict(variables or {}))

    @classmethod
    def cancel(cls, *, view: str | None = None) -> "Transition":
        return cls(TransitionKind.CANCEL, view=view)

    @classmethod
    def fail(cls, error: str) -> "Transition":
        return cls(TransitionKind.FAIL, error=error)

    @classmethod
    def enqueue(cls, task: str, *, payload: Mapping[str, Any] | None = None, delay_seconds: float = 0, view: str | None = None) -> "Transition":
        return cls(TransitionKind.ENQUEUE, view=view, job=JobRequest(task, dict(payload or {}), delay_seconds))


FlowHandler = Callable[["FlowContext", InteractionEvent], Awaitable[Transition]]


@dataclass(frozen=True, slots=True)
class FlowState:
    id: str
    on_enter: FlowHandler | None = None
    on_message: FlowHandler | None = None
    on_callback: FlowHandler | None = None

    def handler_for(self, event: InteractionEvent) -> FlowHandler | None:
        return self.on_message if event.kind == "message" else self.on_callback if event.kind == "callback" else None


@dataclass(frozen=True, slots=True)
class FlowDefinition:
    id: str
    initial_state: str
    states: Mapping[str, FlowState]

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.initial_state.strip():
            raise ValueError("Flow id and initial state are required.")
        if self.initial_state not in self.states:
            raise ValueError(f"Initial state '{self.initial_state}' is not declared in flow '{self.id}'.")
        if any(key != state.id for key, state in self.states.items()):
            raise ValueError("Flow state mapping keys must match FlowState.id.")

    def state(self, state_id: str) -> FlowState:
        try:
            return self.states[state_id]
        except KeyError as error:
            raise KeyError(f"Unknown state '{state_id}' in flow '{self.id}'.") from error
