from __future__ import annotations

import logging
import json
import math
from copy import deepcopy
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .events import CallbackEvent, CommandEvent, InteractionEvent, LifecycleEvent, MessageEvent

_OUTCOME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")


def _validate_json_value(value: Any, *, path: str = "value") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string JSON object key.")
            _validate_json_value(nested, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _validate_json_value(nested, path=f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise TypeError(f"{path} contains a non-finite number.")


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(nested) for key, nested in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(nested) for nested in value)
    return value


@dataclass(frozen=True, slots=True)
class UserInfo:
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True, slots=True)
class ChatInfo:
    id: int


class StateValues:
    """Controlled per-session values exposed to custom business logic."""

    def __init__(self, values: Mapping[str, Any] | None = None) -> None:
        _validate_json_value(values or {}, path="state")
        try:
            json.dumps(dict(values or {}), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise TypeError("State values must be JSON-serializable.") from error
        self._values = deepcopy(dict(values or {}))

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str) or not key:
            raise TypeError("State key must be a non-empty string.")

    def get(self, key: str, default: Any = None) -> Any:
        self._validate_key(key)
        return deepcopy(self._values.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._validate_key(key)
        _validate_json_value(value, path=f"state.{key}")
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise TypeError("State value must be JSON-serializable.") from error
        self._values[key] = deepcopy(value)

    def delete(self, key: str) -> None:
        self._validate_key(key)
        self._values.pop(key, None)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._values)


@dataclass(frozen=True, slots=True)
class HandlerResult:
    outcome_name: str = "success"
    values: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.outcome_name, str) or not _OUTCOME.fullmatch(self.outcome_name):
            raise ValueError("HandlerResult outcome must be a non-empty valid stable identifier.")
        if not isinstance(self.values, Mapping):
            raise TypeError("HandlerResult values must be a mapping.")
        _validate_json_value(self.values, path="HandlerResult.values")
        try:
            json.dumps(dict(self.values), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise TypeError("HandlerResult values must be JSON-serializable.") from error
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))

    @classmethod
    def success(cls, *, values: Mapping[str, Any] | None = None) -> "HandlerResult":
        return cls("success", values or {})

    @classmethod
    def outcome(cls, name: str, *, values: Mapping[str, Any] | None = None) -> "HandlerResult":
        return cls(name, values or {})


@dataclass(frozen=True, slots=True)
class BaseHandlerContext:
    user: UserInfo
    chat: ChatInfo
    event: InteractionEvent
    payload: Mapping[str, Any]
    state: StateValues
    services: Mapping[str, Any]
    logger: logging.Logger

    def __post_init__(self) -> None:
        _validate_json_value(self.payload, path="context.payload")
        object.__setattr__(self, "payload", _freeze_json(dict(self.payload)))
        object.__setattr__(self, "services", MappingProxyType(dict(self.services)))


@dataclass(frozen=True, slots=True)
class ButtonContext(BaseHandlerContext):
    event: CallbackEvent


@dataclass(frozen=True, slots=True)
class MessageContext(BaseHandlerContext):
    event: MessageEvent


@dataclass(frozen=True, slots=True)
class CommandContext(BaseHandlerContext):
    event: CommandEvent


@dataclass(frozen=True, slots=True)
class LifecycleContext(BaseHandlerContext):
    event: LifecycleEvent


@dataclass(frozen=True, slots=True)
class TaskContext:
    job_id: str
    payload: Mapping[str, Any]
    services: Mapping[str, Any]
    logger: logging.Logger

    def __post_init__(self) -> None:
        _validate_json_value(self.payload, path="context.payload")
        object.__setattr__(self, "payload", _freeze_json(dict(self.payload)))
        object.__setattr__(self, "services", MappingProxyType(dict(self.services)))
