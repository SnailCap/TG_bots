from __future__ import annotations

from typing import Callable, Type, Any

from .registry import UiRegistry, EntityKind

_default_registry = UiRegistry()


def get_default_ui_registry() -> UiRegistry:
    return _default_registry


def _bind(kind: EntityKind, key: str) -> Callable[[Type[Any]], Type[Any]]:
    def decorator(cls: Type[Any]) -> Type[Any]:
        get_default_ui_registry().register(kind, key, cls)
        setattr(cls, "__ui_kind__", kind)
        setattr(cls, "__ui_key__", key)
        return cls
    return decorator


def page(key: str) -> Callable[[Type[Any]], Type[Any]]:
    return _bind("page", key)


def step(key: str) -> Callable[[Type[Any]], Type[Any]]:
    return _bind("step", key)


def notification(key: str) -> Callable[[Type[Any]], Type[Any]]:
    return _bind("notification", key)


def process(key: str) -> Callable[[Type[Any]], Type[Any]]:
    return _bind("process", key)