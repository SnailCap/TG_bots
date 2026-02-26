from __future__ import annotations

from dataclasses import dataclass
from typing import Type, Any

from .registry import UiRegistry, EntityKind
from .decorators import get_default_registry


@dataclass(frozen=True, slots=True)
class UiClassResolver:
    """
    Выбирает класс:
    - если есть кастомный — возвращает его
    - иначе — базовый, который передали как default_cls
    """
    registry: UiRegistry

    @classmethod
    def default(cls) -> "UiClassResolver":
        return cls(registry=get_default_registry())

    def resolve(self, kind: EntityKind, key: str, default_cls: Type[Any]) -> Type[Any]:
        found = self.registry.get(kind, key)
        return found if found is not None else default_cls

    def resolve_page(self, key: str, default_cls: Type[Any]) -> Type[Any]:
        return self.resolve("page", key, default_cls)

    def resolve_step(self, key: str, default_cls: Type[Any]) -> Type[Any]:
        return self.resolve("step", key, default_cls)

    def resolve_notification(self, key: str, default_cls: Type[Any]) -> Type[Any]:
        return self.resolve("notification", key, default_cls)