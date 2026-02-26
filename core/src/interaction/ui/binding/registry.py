from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Type, Literal, Any

from .errors import DuplicateBindingError

EntityKind = Literal["page", "step", "notification", "process"]


@dataclass(slots=True)
class UiRegistry:
    _store: Dict[EntityKind, Dict[str, Type[Any]]] = field(
        default_factory=lambda: {
            "page": {},
            "step": {},
            "notification": {},
            "process": {},
        },
        init=False,
        repr=False,
    )

    def register(self, kind: EntityKind, key: str, cls: Type[Any]) -> None:
        bucket = self._store[kind]
        if key in bucket:
            prev = bucket[key]
            raise DuplicateBindingError(
                f"Duplicate binding for {kind} '{key}': {prev.__module__}.{prev.__name__} "
                f"and {cls.__module__}.{cls.__name__}"
            )
        bucket[key] = cls

    def get(self, kind: EntityKind, key: str) -> Type[Any] | None:
        return self._store[kind].get(key)

    def all(self, kind: EntityKind) -> Dict[str, Type[Any]]:
        return dict(self._store[kind])
