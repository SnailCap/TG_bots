from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .context import ActionContext
from .decorators import get_action_name
from .result import ActionResult

ActionCallable = Callable[[ActionContext], Awaitable[ActionResult]]


@dataclass(frozen=True, slots=True)
class RegisteredAction:
    name: str
    function: ActionCallable
    module: str
    file_path: str | None = None
    line: int | None = None


@dataclass(slots=True)
class ActionRegistry:
    _actions: dict[str, RegisteredAction] = field(default_factory=dict)

    def register(
        self,
        function: ActionCallable,
        *,
        module: str | None = None,
        file_path: str | None = None,
        line: int | None = None,
    ) -> RegisteredAction:
        name = get_action_name(function)
        if name is None:
            raise ValueError("Action function is missing the @action decorator")
        if name in self._actions:
            raise ValueError(f"Duplicate action registration: {name}")
        registered = RegisteredAction(
            name=name,
            function=function,
            module=module or function.__module__,
            file_path=file_path,
            line=line,
        )
        self._actions[name] = registered
        return registered

    def get(self, name: str) -> RegisteredAction | None:
        return self._actions.get(name)

    def require(self, name: str) -> RegisteredAction:
        result = self.get(name)
        if result is None:
            raise KeyError(f"Unknown action: {name}")
        return result

    def all(self) -> tuple[RegisteredAction, ...]:
        return tuple(self._actions[name] for name in sorted(self._actions))

