from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any


ServiceFactory = Callable[["ServiceContainer"], Any | Awaitable[Any]]
ServiceDisposer = Callable[[Any], None | Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ServiceProvider:
    key: str
    factory: ServiceFactory
    disposer: ServiceDisposer | None = None


class ServiceContainer:
    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._cleanup: list[tuple[Any, ServiceDisposer | None, Any | None]] = []

    async def build(self, providers: Sequence[ServiceProvider]) -> None:
        try:
            for provider in providers:
                if provider.key in self._services:
                    raise ValueError(f"Duplicate service provider '{provider.key}'.")
                value = provider.factory(self)
                value = await value if inspect.isawaitable(value) else value
                manager = None
                if hasattr(value, "__aenter__") and hasattr(value, "__aexit__"):
                    manager = value
                    value = await manager.__aenter__()
                self._services[provider.key] = value
                self._cleanup.append((value, provider.disposer, manager))
        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        errors: list[BaseException] = []
        for value, disposer, manager in reversed(self._cleanup):
            try:
                if manager is not None:
                    await manager.__aexit__(None, None, None)
                elif disposer is not None:
                    result = disposer(value)
                    if inspect.isawaitable(result):
                        await result
                elif hasattr(value, "aclose"):
                    result = value.aclose()
                    if inspect.isawaitable(result):
                        await result
                elif hasattr(value, "close"):
                    result = value.close()
                    if inspect.isawaitable(result):
                        await result
            except BaseException as error:
                errors.append(error)
        self._cleanup.clear()
        self._services.clear()
        if errors:
            raise ExceptionGroup("One or more services failed to close.", errors)

    def get(self, key: str) -> Any:
        try:
            return self._services[key]
        except KeyError as error:
            raise KeyError(f"Service '{key}' is not registered.") from error

    def all(self) -> Mapping[str, Any]:
        return dict(self._services)
