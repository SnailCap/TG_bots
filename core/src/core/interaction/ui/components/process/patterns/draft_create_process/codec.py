from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Generic, TypeVar

from .schema import DraftSchema

DraftT = TypeVar("DraftT")


class DraftCodec(Generic[DraftT]):
    """
    Serializes/deserializes draft objects through schema field specs.

    Requirements for draft objects:
    - dataclass, or
    - object with __dict__, or
    - callable draft_factory(**kwargs) must accept partial kwargs
    """

    def __init__(
        self,
        *,
        schema: DraftSchema[DraftT],
        draft_factory: Callable[..., DraftT],
    ) -> None:
        self._schema = schema
        self._draft_factory = draft_factory

    def dump(self, draft: DraftT) -> dict[str, Any]:
        raw = self._as_mapping(draft)
        result: dict[str, Any] = {}

        for field_spec in self._schema.fields:
            result[field_spec.name] = field_spec.dump_value(raw.get(field_spec.name))

        return result

    def load(self, payload: dict[str, Any] | None) -> DraftT:
        payload = payload or {}
        kwargs: dict[str, Any] = {}

        for field_spec in self._schema.fields:
            kwargs[field_spec.name] = field_spec.load_value(payload.get(field_spec.name))

        return self._draft_factory(**kwargs)

    def merge(self, *, base: DraftT, patch: DraftT) -> DraftT:
        base_map = self._as_mapping(base)
        patch_map = self._as_mapping(patch)

        merged = dict(base_map)
        for field_spec in self._schema.fields:
            patch_value = patch_map.get(field_spec.name)
            if patch_value is not None:
                merged[field_spec.name] = patch_value

        return self._draft_factory(**merged)

    @staticmethod
    def as_mapping(draft: DraftT) -> dict[str, Any]:
        return DraftCodec._as_mapping(draft)

    @staticmethod
    def _as_mapping(draft: DraftT) -> dict[str, Any]:
        if is_dataclass(draft):
            return asdict(draft)

        if hasattr(draft, "__dict__"):
            return dict(vars(draft))

        raise TypeError(
            "DraftCodec supports dataclasses or objects with __dict__ only."
        )