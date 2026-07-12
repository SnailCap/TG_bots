from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .flows import FlowDefinition
from .jobs import ScheduleSpec, TaskHandler


ServiceFactory = Callable[["Container"], Any | Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class ServiceProvider:
    key: str
    factory: ServiceFactory


class Container:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    async def build(self, providers: Sequence[ServiceProvider]) -> None:
        for provider in providers:
            if provider.key in self._services:
                raise ValueError(f"Duplicate service provider: {provider.key}")
            value = provider.factory(self)
            self._services[provider.key] = await value if inspect.isawaitable(value) else value

    def get(self, key: str) -> Any:
        try:
            return self._services[key]
        except KeyError as error:
            raise KeyError(f"Service '{key}' is not registered.") from error

    def all(self) -> Mapping[str, Any]:
        return dict(self._services)


@dataclass(frozen=True, slots=True)
class BotModule:
    """All app extension points are explicit data, never import side effects."""

    flows: Sequence[FlowDefinition]
    services: Sequence[ServiceProvider] = ()
    task_handlers: Mapping[str, TaskHandler] = field(default_factory=dict)
    schedules: Sequence[ScheduleSpec] = ()

    def flow_map(self) -> dict[str, FlowDefinition]:
        flows = {flow.id: flow for flow in self.flows}
        if len(flows) != len(self.flows):
            raise ValueError("Flow ids must be unique.")
        return flows

    def task_map(self) -> dict[str, TaskHandler]:
        if any(not name.strip() for name in self.task_handlers):
            raise ValueError("Task handler names must not be empty.")
        return dict(self.task_handlers)
