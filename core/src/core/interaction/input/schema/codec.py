from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Generic, TypeVar

from .object_schema import ObjectSchema
from .results import ObjectBuildResult

ObjectT = TypeVar("ObjectT")


class InputCodec(Generic[ObjectT]):
    """
    Object <-> mapping codec based on ObjectSchema field specs.

    Supported object kinds:
    - dataclass
    - object with __dict__
    """

    def __init__(self, *, schema: ObjectSchema[ObjectT]) -> None:
        self._schema = schema

    def dump(self, obj: ObjectT) -> dict[str, Any]:
        raw = self.as_mapping(obj)
        result: dict[str, Any] = {}

        for field_spec in self._schema.fields:
            result[field_spec.name] = field_spec.dump_value(raw.get(field_spec.name))

        return result

    def load(self, payload: dict[str, Any] | None) -> ObjectT:
        payload = payload or {}
        kwargs: dict[str, Any] = {}

        for field_spec in self._schema.fields:
            kwargs[field_spec.name] = field_spec.load_value(payload.get(field_spec.name))

        return self._schema.object_factory(**kwargs)

    def patch_object(
        self,
        *,
        base: ObjectT,
        patch_values: dict[str, Any],
    ) -> ObjectBuildResult[ObjectT]:
        base_map = self.as_mapping(base)
        merged = dict(base_map)
        merged.update({k: v for k, v in patch_values.items() if v is not None})
        return self._schema.build_object(merged)

    @staticmethod
    def as_mapping(obj: ObjectT) -> dict[str, Any]:
        if is_dataclass(obj):
            return asdict(obj)

        if hasattr(obj, "__dict__"):
            return dict(vars(obj))

        raise TypeError("InputCodec supports dataclasses or objects with __dict__ only.")