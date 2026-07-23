from __future__ import annotations

import json
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, TypeAlias
from uuid import uuid4

import aiosqlite

from .events import Actor

log = logging.getLogger(__name__)

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
MAX_METADATA_BYTES = 8 * 1024


class AnalyticsEventType(StrEnum):
    USER_FIRST_SEEN = "user_first_seen"
    INTERACTION_RECEIVED = "interaction_received"
    COMMAND_RECEIVED = "command_received"
    MESSAGE_RECEIVED = "message_received"
    BUTTON_CLICKED = "button_clicked"
    VIEW_RENDERED = "view_rendered"
    FLOW_STARTED = "flow_started"
    FLOW_COMPLETED = "flow_completed"
    FLOW_CANCELLED = "flow_cancelled"
    FLOW_FAILED = "flow_failed"
    STATE_ENTERED = "state_entered"
    STATE_EXITED = "state_exited"
    HANDLER_STARTED = "handler_started"
    HANDLER_SUCCEEDED = "handler_succeeded"
    HANDLER_FAILED = "handler_failed"


@dataclass(frozen=True, slots=True)
class AnalyticsEvent:
    id: str
    bot_id: str
    user_id: int | None
    chat_id: int | None
    session_id: str | None
    event_type: AnalyticsEventType
    resource_type: str | None
    resource_id: str | None
    flow_id: str | None
    state_id: str | None
    view_id: str | None
    handler_id: str | None
    outcome: str | None
    status: str | None
    occurred_at: datetime
    metadata_json: str


@dataclass(frozen=True, slots=True)
class AnalyticsEventSpec:
    actor_required: bool = True
    required_fields: frozenset[str] = frozenset()
    allowed_fields: frozenset[str] = frozenset()
    resource_type: str | None = None
    resource_field: str | None = None
    status: str | None = None
    allowed_metadata: frozenset[str] = frozenset()
    required_metadata: frozenset[str] = frozenset()


_HANDLER_CONTEXT_METADATA = frozenset({"handler_kind", "job_id"})

ANALYTICS_EVENT_SPECS: Mapping[AnalyticsEventType, AnalyticsEventSpec] = {
    AnalyticsEventType.USER_FIRST_SEEN: AnalyticsEventSpec(),
    AnalyticsEventType.INTERACTION_RECEIVED: AnalyticsEventSpec(),
    AnalyticsEventType.COMMAND_RECEIVED: AnalyticsEventSpec(
        required_fields=frozenset({"resource_id"}),
        allowed_fields=frozenset({"resource_id"}),
        resource_type="command",
        resource_field="resource_id",
    ),
    AnalyticsEventType.MESSAGE_RECEIVED: AnalyticsEventSpec(),
    AnalyticsEventType.BUTTON_CLICKED: AnalyticsEventSpec(
        required_fields=frozenset({"resource_id"}),
        allowed_fields=frozenset({"resource_id", "flow_id", "state_id", "view_id"}),
        resource_type="button",
        resource_field="resource_id",
    ),
    AnalyticsEventType.VIEW_RENDERED: AnalyticsEventSpec(
        required_fields=frozenset({"view_id"}),
        allowed_fields=frozenset({"flow_id", "state_id", "view_id"}),
        resource_type="view",
        resource_field="view_id",
    ),
    AnalyticsEventType.FLOW_STARTED: AnalyticsEventSpec(
        required_fields=frozenset({"flow_id"}),
        allowed_fields=frozenset({"flow_id"}),
        resource_type="flow",
        resource_field="flow_id",
        status="active",
    ),
    AnalyticsEventType.FLOW_COMPLETED: AnalyticsEventSpec(
        required_fields=frozenset({"flow_id"}),
        allowed_fields=frozenset({"flow_id"}),
        resource_type="flow",
        resource_field="flow_id",
        status="finished",
    ),
    AnalyticsEventType.FLOW_CANCELLED: AnalyticsEventSpec(
        required_fields=frozenset({"flow_id"}),
        allowed_fields=frozenset({"flow_id"}),
        resource_type="flow",
        resource_field="flow_id",
        status="cancelled",
    ),
    AnalyticsEventType.FLOW_FAILED: AnalyticsEventSpec(
        required_fields=frozenset({"flow_id"}),
        allowed_fields=frozenset({"flow_id"}),
        resource_type="flow",
        resource_field="flow_id",
        status="failed",
    ),
    AnalyticsEventType.STATE_ENTERED: AnalyticsEventSpec(
        required_fields=frozenset({"flow_id", "state_id"}),
        allowed_fields=frozenset({"flow_id", "state_id"}),
        resource_type="state",
        resource_field="state_id",
    ),
    AnalyticsEventType.STATE_EXITED: AnalyticsEventSpec(
        required_fields=frozenset({"flow_id", "state_id"}),
        allowed_fields=frozenset({"flow_id", "state_id"}),
        resource_type="state",
        resource_field="state_id",
    ),
    AnalyticsEventType.HANDLER_STARTED: AnalyticsEventSpec(
        actor_required=False,
        required_fields=frozenset({"handler_id"}),
        allowed_fields=frozenset({"flow_id", "state_id", "view_id", "handler_id"}),
        resource_type="handler",
        resource_field="handler_id",
        status="started",
        allowed_metadata=_HANDLER_CONTEXT_METADATA,
        required_metadata=frozenset({"handler_kind"}),
    ),
    AnalyticsEventType.HANDLER_SUCCEEDED: AnalyticsEventSpec(
        actor_required=False,
        required_fields=frozenset({"handler_id", "outcome"}),
        allowed_fields=frozenset(
            {"flow_id", "state_id", "view_id", "handler_id", "outcome"}
        ),
        resource_type="handler",
        resource_field="handler_id",
        status="succeeded",
        allowed_metadata=_HANDLER_CONTEXT_METADATA | {"duration_ms"},
        required_metadata=frozenset({"handler_kind", "duration_ms"}),
    ),
    AnalyticsEventType.HANDLER_FAILED: AnalyticsEventSpec(
        actor_required=False,
        required_fields=frozenset({"handler_id"}),
        allowed_fields=frozenset({"flow_id", "state_id", "view_id", "handler_id"}),
        resource_type="handler",
        resource_field="handler_id",
        status="failed",
        allowed_metadata=_HANDLER_CONTEXT_METADATA | {"duration_ms", "error_type"},
        required_metadata=frozenset({"handler_kind", "duration_ms", "error_type"}),
    ),
}


class AnalyticsEventWriter(Protocol):
    async def append(self, event: AnalyticsEvent) -> None: ...


class SqliteAnalyticsEventWriter:
    def __init__(self, path: Path) -> None:
        self._path = path

    async def append(self, event: AnalyticsEvent) -> None:
        async with aiosqlite.connect(self._path) as connection:
            await connection.execute(
                """
                INSERT INTO analytics_events (
                    id, bot_id, user_id, chat_id, session_id, event_type,
                    resource_type, resource_id, flow_id, state_id, view_id,
                    handler_id, outcome, status, occurred_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.bot_id,
                    event.user_id,
                    event.chat_id,
                    event.session_id,
                    event.event_type.value,
                    event.resource_type,
                    event.resource_id,
                    event.flow_id,
                    event.state_id,
                    event.view_id,
                    event.handler_id,
                    event.outcome,
                    event.status,
                    event.occurred_at.timestamp(),
                    event.metadata_json,
                ),
            )
            await connection.commit()


class AnalyticsRecorder:
    """Build, validate and append analytics events without affecting runtime success."""

    def __init__(self, bot_id: str, writer: AnalyticsEventWriter) -> None:
        self.bot_id = bot_id
        self._writer = writer

    async def record(
        self,
        event_type: AnalyticsEventType,
        *,
        actor: Actor | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        flow_id: str | None = None,
        state_id: str | None = None,
        view_id: str | None = None,
        handler_id: str | None = None,
        outcome: str | None = None,
        status: str | None = None,
        metadata: Mapping[str, JsonValue] | None = None,
    ) -> bool:
        try:
            event = build_analytics_event(
                bot_id=self.bot_id,
                event_type=event_type,
                actor=actor,
                resource_type=resource_type,
                resource_id=resource_id,
                flow_id=flow_id,
                state_id=state_id,
                view_id=view_id,
                handler_id=handler_id,
                outcome=outcome,
                status=status,
                metadata=metadata,
            )
            await self._writer.append(event)
        except Exception:
            log.exception(
                "Could not record analytics event: bot_id=%s event_type=%s",
                self.bot_id,
                getattr(event_type, "value", str(event_type)),
            )
            return False
        return True


def build_analytics_event(
    *,
    bot_id: str,
    event_type: AnalyticsEventType,
    actor: Actor | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    flow_id: str | None = None,
    state_id: str | None = None,
    view_id: str | None = None,
    handler_id: str | None = None,
    outcome: str | None = None,
    status: str | None = None,
    metadata: Mapping[str, JsonValue] | None = None,
    event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> AnalyticsEvent:
    if not bot_id:
        raise ValueError("Analytics event requires a non-empty bot_id.")
    spec = ANALYTICS_EVENT_SPECS[event_type]
    if spec.actor_required and actor is None:
        raise ValueError(f"Analytics event '{event_type.value}' requires an actor.")

    fields: dict[str, str | None] = {
        "resource_id": resource_id,
        "flow_id": flow_id,
        "state_id": state_id,
        "view_id": view_id,
        "handler_id": handler_id,
        "outcome": outcome,
    }
    missing = sorted(name for name in spec.required_fields if not fields[name])
    if missing:
        raise ValueError(
            f"Analytics event '{event_type.value}' requires fields: {', '.join(missing)}."
        )
    unexpected_fields = sorted(
        name for name, value in fields.items() if value is not None and name not in spec.allowed_fields
    )
    if unexpected_fields:
        raise ValueError(
            f"Analytics event '{event_type.value}' does not allow fields: "
            f"{', '.join(unexpected_fields)}."
        )

    if spec.resource_type is not None:
        if resource_type not in (None, spec.resource_type):
            raise ValueError(
                f"Analytics event '{event_type.value}' requires resource_type "
                f"'{spec.resource_type}'."
            )
        resource_type = spec.resource_type
        if spec.resource_field is not None:
            expected_resource_id = fields[spec.resource_field]
            if resource_id not in (None, expected_resource_id):
                raise ValueError(
                    f"Analytics event '{event_type.value}' has an inconsistent resource_id."
                )
            resource_id = expected_resource_id
    elif resource_type is not None or resource_id is not None:
        raise ValueError(
            f"Analytics event '{event_type.value}' does not allow a resource reference."
        )

    if spec.status is not None:
        if status not in (None, spec.status):
            raise ValueError(
                f"Analytics event '{event_type.value}' requires status '{spec.status}'."
            )
        status = spec.status
    elif status is not None:
        raise ValueError(f"Analytics event '{event_type.value}' does not allow status.")

    metadata_values = dict(metadata or {})
    unexpected_metadata = sorted(set(metadata_values) - spec.allowed_metadata)
    if unexpected_metadata:
        raise ValueError(
            f"Analytics event '{event_type.value}' does not allow metadata keys: "
            f"{', '.join(unexpected_metadata)}."
        )
    missing_metadata = sorted(spec.required_metadata - set(metadata_values))
    if missing_metadata:
        raise ValueError(
            f"Analytics event '{event_type.value}' requires metadata keys: "
            f"{', '.join(missing_metadata)}."
        )
    _validate_handler_metadata(metadata_values)
    metadata_json = serialize_metadata(metadata_values)

    timestamp = occurred_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ValueError("Analytics occurred_at must be timezone-aware.")
    return AnalyticsEvent(
        id=event_id or str(uuid4()),
        bot_id=bot_id,
        user_id=actor.user_id if actor else None,
        chat_id=actor.chat_id if actor else None,
        session_id=None,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        flow_id=flow_id,
        state_id=state_id,
        view_id=view_id,
        handler_id=handler_id,
        outcome=outcome,
        status=status,
        occurred_at=timestamp.astimezone(UTC),
        metadata_json=metadata_json,
    )


def serialize_metadata(metadata: Mapping[str, JsonValue]) -> str:
    if not isinstance(metadata, Mapping):
        raise TypeError("Analytics metadata must be a mapping.")
    normalized = _validate_json_mapping(metadata)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise ValueError(f"Analytics metadata exceeds {MAX_METADATA_BYTES} bytes.")
    return encoded


def _validate_json_mapping(value: Mapping[Any, Any]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("Analytics metadata object keys must be strings.")
        result[key] = _validate_json_value(item)
    return result


def _validate_json_value(value: Any) -> JsonValue:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("Analytics metadata numbers must be finite.")
        return value
    if isinstance(value, list):
        return [_validate_json_value(item) for item in value]
    if isinstance(value, Mapping):
        return _validate_json_mapping(value)
    raise TypeError(
        "Analytics metadata values must be JSON-serializable safe values."
    )


def _validate_handler_metadata(metadata: Mapping[str, JsonValue]) -> None:
    for key in ("handler_kind", "job_id", "error_type"):
        value = metadata.get(key)
        if value is not None and (not isinstance(value, str) or not value):
            raise TypeError(f"Analytics metadata '{key}' must be a non-empty string.")
    duration = metadata.get("duration_ms")
    if duration is not None and (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration < 0
    ):
        raise TypeError("Analytics metadata 'duration_ms' must be a finite non-negative number.")


async def initialize_analytics_schema(connection: aiosqlite.Connection) -> None:
    await connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS analytics_events (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            user_id INTEGER,
            chat_id INTEGER,
            session_id TEXT,
            event_type TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            flow_id TEXT,
            state_id TEXT,
            view_id TEXT,
            handler_id TEXT,
            outcome TEXT,
            status TEXT,
            occurred_at REAL NOT NULL,
            metadata_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS analytics_events_bot_time_idx
            ON analytics_events (bot_id, occurred_at);
        CREATE INDEX IF NOT EXISTS analytics_events_bot_user_time_idx
            ON analytics_events (bot_id, user_id, occurred_at);
        CREATE INDEX IF NOT EXISTS analytics_events_bot_type_time_idx
            ON analytics_events (bot_id, event_type, occurred_at);
        CREATE INDEX IF NOT EXISTS analytics_events_bot_resource_time_idx
            ON analytics_events (bot_id, resource_type, resource_id, occurred_at);
        """
    )
