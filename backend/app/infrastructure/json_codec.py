from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

_TYPE_KEY = "$botstudio_type"


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {_TYPE_KEY: "decimal", "value": str(value)}
    if isinstance(value, datetime):
        return {_TYPE_KEY: "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {_TYPE_KEY: "date", "value": value.isoformat()}
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")


def _object_hook(value: dict[str, Any]) -> Any:
    kind = value.get(_TYPE_KEY)
    if kind == "decimal" and set(value) == {_TYPE_KEY, "value"}:
        return Decimal(str(value["value"]))
    if kind == "datetime" and set(value) == {_TYPE_KEY, "value"}:
        return datetime.fromisoformat(str(value["value"]))
    if kind == "date" and set(value) == {_TYPE_KEY, "value"}:
        return date.fromisoformat(str(value["value"]))
    return value


def dumps_json(value: Any, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        default=_default,
    )


def loads_json(content: str) -> Any:
    return json.loads(content, object_hook=_object_hook)

