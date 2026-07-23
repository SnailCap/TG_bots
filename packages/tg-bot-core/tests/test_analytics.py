from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import aiosqlite
import pytest

from tg_bot_core import Actor, CallbackEvent, CommandEvent, MessageEvent
from tg_bot_core.analytics import (
    MAX_METADATA_BYTES,
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsRecorder,
    build_analytics_event,
    serialize_metadata,
)
from tg_bot_core.handlers import HandlerExecutor, HandlerResolver
from tg_bot_core.project import HandlerBinding
from tg_bot_core.sdk import TaskContext
from tg_bot_core.store import SqliteStore

from conftest import FakeTransport, write_handler
from test_runtime_v3 import make_interactive_project, new_app


class CapturingWriter:
    def __init__(self) -> None:
        self.events: list[AnalyticsEvent] = []

    async def append(self, event: AnalyticsEvent) -> None:
        self.events.append(event)


class FailingWriter:
    async def append(self, event: AnalyticsEvent) -> None:
        raise RuntimeError(f"analytics unavailable for {event.event_type.value}")


async def read_events(database: Path) -> list[dict[str, object]]:
    async with aiosqlite.connect(database) as connection:
        connection.row_factory = aiosqlite.Row
        rows = await (
            await connection.execute(
                "SELECT * FROM analytics_events ORDER BY occurred_at, rowid"
            )
        ).fetchall()
    return [dict(row) for row in rows]


@pytest.mark.asyncio
async def test_typed_recorder_builds_uuid_timestamp_and_resource_snapshot() -> None:
    writer = CapturingWriter()
    recorder = AnalyticsRecorder("bot-one", writer)
    actor = Actor(7, 8)

    assert await recorder.record(
        AnalyticsEventType.VIEW_RENDERED,
        actor=actor,
        flow_id="checkout",
        state_id="confirm",
        view_id="confirm-view",
    )

    event = writer.events[0]
    assert UUID(event.id)
    assert event.occurred_at.tzinfo is UTC
    assert (event.resource_type, event.resource_id) == ("view", "confirm-view")
    assert (event.user_id, event.chat_id, event.session_id) == (7, 8, None)
    assert json.loads(event.metadata_json) == {}


def test_metadata_serializer_accepts_only_bounded_safe_json() -> None:
    assert json.loads(
        serialize_metadata(
            {
                "none": None,
                "boolean": True,
                "integer": 3,
                "float": 1.5,
                "string": "safe",
                "list": [1, {"nested": "value"}],
            }
        )
    )["list"] == [1, {"nested": "value"}]

    with pytest.raises(TypeError, match="keys must be strings"):
        serialize_metadata({1: "value"})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match="finite"):
        serialize_metadata({"value": float("nan")})
    with pytest.raises(TypeError, match="safe values"):
        serialize_metadata({"value": ("tuple",)})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match=str(MAX_METADATA_BYTES)):
        serialize_metadata({"value": "x" * MAX_METADATA_BYTES})


def test_event_catalog_rejects_unknown_metadata_and_inconsistent_fields() -> None:
    actor = Actor(1, 2)
    with pytest.raises(ValueError, match="does not allow metadata keys"):
        build_analytics_event(
            bot_id="bot",
            event_type=AnalyticsEventType.MESSAGE_RECEIVED,
            actor=actor,
            metadata={"message_text": "secret"},
        )
    with pytest.raises(ValueError, match="does not allow fields"):
        build_analytics_event(
            bot_id="bot",
            event_type=AnalyticsEventType.USER_FIRST_SEEN,
            actor=actor,
            view_id="unexpected",
        )
    with pytest.raises(ValueError, match="requires fields"):
        build_analytics_event(
            bot_id="bot",
            event_type=AnalyticsEventType.STATE_ENTERED,
            actor=actor,
            flow_id="main",
        )
    with pytest.raises(ValueError, match="requires status"):
        build_analytics_event(
            bot_id="bot",
            event_type=AnalyticsEventType.FLOW_COMPLETED,
            actor=actor,
            flow_id="main",
            status="failed",
        )


@pytest.mark.asyncio
async def test_existing_database_gains_analytics_table_and_indices_without_data_loss(
    tmp_path: Path,
) -> None:
    database = tmp_path / "runtime.sqlite3"
    store = SqliteStore(database)
    await store.initialize()
    actor = Actor(10, 20)
    await store.upsert_user("bot", actor)
    await store.save_session(await store.load_session("bot", actor))
    await store.mark_update_once("bot", actor, 99)
    async with aiosqlite.connect(database) as connection:
        await connection.execute(
            """INSERT INTO jobs
            VALUES ('job', 'handler', '{}', 0, 'queued', 0, 1, NULL, NULL, 0, 0)"""
        )
        await connection.execute(
            """INSERT INTO schedules
            VALUES ('schedule', 'handler', '{}', 60, 0, 1, 0)"""
        )
        await connection.execute(
            """INSERT INTO job_runs
            VALUES ('run', 'job', 0, NULL, 'processing', NULL)"""
        )
        await connection.execute("DROP TABLE analytics_events")
        await connection.commit()

    await SqliteStore(database).initialize()

    async with aiosqlite.connect(database) as connection:
        table = await (
            await connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_events'"
            )
        ).fetchone()
        indices = {
            row[1]
            for row in await (
                await connection.execute("PRAGMA index_list(analytics_events)")
            ).fetchall()
        }
        counts = {}
        for name in (
            "bot_users",
            "flow_sessions",
            "processed_updates",
            "jobs",
            "schedules",
            "job_runs",
        ):
            counts[name] = (
                await (await connection.execute(f"SELECT count(*) FROM {name}")).fetchone()
            )[0]
    assert table is not None
    assert {
        "analytics_events_bot_time_idx",
        "analytics_events_bot_user_time_idx",
        "analytics_events_bot_type_time_idx",
        "analytics_events_bot_resource_time_idx",
    } <= indices
    assert counts == {
        "bot_users": 1,
        "flow_sessions": 1,
        "processed_updates": 1,
        "jobs": 1,
        "schedules": 1,
        "job_runs": 1,
    }


@pytest.mark.asyncio
async def test_runtime_records_inputs_views_lifecycle_and_handlers(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    actor = Actor(31, 32)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start", "private arguments"))
    await transport.emit(CommandEvent(actor, 2, "help"))
    await transport.emit(MessageEvent(actor, 3, "valid"))
    await transport.emit(CallbackEvent(actor, 4, "confirm_order"))

    events = await read_events(tmp_path / "data" / "runtime.sqlite3")
    actor_events = [row for row in events if row["user_id"] == actor.user_id]
    event_types = [row["event_type"] for row in actor_events]
    assert event_types.count("user_first_seen") == 1
    assert event_types.count("interaction_received") == 4
    assert event_types.count("command_received") == 2
    assert event_types.count("message_received") == 1
    assert event_types.count("button_clicked") == 1
    assert event_types.count("flow_started") == 1
    assert event_types.count("state_entered") == 2
    assert event_types.count("state_exited") == 2
    assert event_types.count("flow_completed") == 1
    assert event_types.count("view_rendered") == 4

    command = next(row for row in actor_events if row["event_type"] == "command_received")
    assert (command["resource_type"], command["resource_id"]) == ("command", "start")
    assert "private arguments" not in json.dumps(events)
    assert '"valid"' not in json.dumps(events)
    button = next(row for row in actor_events if row["event_type"] == "button_clicked")
    assert (
        button["resource_type"],
        button["resource_id"],
        button["flow_id"],
        button["state_id"],
        button["view_id"],
    ) == ("button", "confirm_order", "main", "confirm", "confirm")

    transitions = [
        (row["event_type"], row["state_id"])
        for row in actor_events
        if row["event_type"] in {"state_entered", "state_exited"}
    ]
    assert transitions == [
        ("state_entered", "ask"),
        ("state_exited", "ask"),
        ("state_entered", "confirm"),
        ("state_exited", "confirm"),
    ]
    completed = next(
        row for row in actor_events if row["event_type"] == "flow_completed"
    )
    assert (completed["flow_id"], completed["status"]) == ("main", "finished")
    succeeded = [
        row for row in actor_events if row["event_type"] == "handler_succeeded"
    ]
    assert succeeded
    assert all(row["status"] == "succeeded" for row in succeeded)
    assert all(json.loads(row["metadata_json"])["duration_ms"] >= 0 for row in succeeded)
    await app.stop()


@pytest.mark.asyncio
async def test_cancelled_flow_records_cancel_status(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    actor = Actor(35, 36)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(MessageEvent(actor, 2, "valid"))
    await transport.emit(CallbackEvent(actor, 3, "cancel_order"))

    events = await read_events(tmp_path / "data" / "runtime.sqlite3")
    cancelled = next(row for row in events if row["event_type"] == "flow_cancelled")
    assert (cancelled["flow_id"], cancelled["status"]) == ("main", "cancelled")
    assert not any(row["event_type"] == "flow_completed" for row in events)
    await app.stop()


@pytest.mark.asyncio
async def test_optimistic_retry_repeats_handlers_but_not_lifecycle_events(
    tmp_path: Path,
) -> None:
    make_interactive_project(tmp_path)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    actor = Actor(37, 38)
    await app.start()
    original_save = app.store.save_session
    saves = 0

    async def conflict_once(session):
        nonlocal saves
        saves += 1
        if saves == 1:
            from tg_bot_core.store import SessionConflict

            raise SessionConflict("simulated")
        return await original_save(session)

    app.store.save_session = conflict_once  # type: ignore[method-assign]
    await transport.emit(CommandEvent(actor, 1, "start"))

    events = await read_events(tmp_path / "data" / "runtime.sqlite3")
    starts = [
        row
        for row in events
        if row["event_type"] == "handler_started"
        and row["handler_id"] == "life.start"
    ]
    successes = [
        row
        for row in events
        if row["event_type"] == "handler_succeeded"
        and row["handler_id"] == "life.start"
    ]
    assert len(starts) == len(successes) == 2
    assert sum(row["event_type"] == "flow_started" for row in events) == 1
    assert sum(row["event_type"] == "state_entered" for row in events) == 1
    await app.stop()


@pytest.mark.asyncio
async def test_failed_handler_records_safe_failure_and_failed_flow(tmp_path: Path) -> None:
    make_interactive_project(tmp_path)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    actor = Actor(41, 42)
    await app.start()

    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(MessageEvent(actor, 2, "explode"))

    events = await read_events(tmp_path / "data" / "runtime.sqlite3")
    failure = next(
        row
        for row in events
        if row["event_type"] == "handler_failed"
        and row["handler_id"] == "profile.save"
    )
    assert failure["status"] == "failed"
    assert json.loads(failure["metadata_json"])["error_type"] == "HandlerExecutionError"
    assert any(
        row["event_type"] == "flow_failed"
        and row["flow_id"] == "main"
        and row["status"] == "failed"
        for row in events
    )
    assert "returned NoneType" not in failure["metadata_json"]
    await app.stop()


@pytest.mark.asyncio
async def test_first_seen_is_unique_and_blocked_user_only_gets_input_events(
    tmp_path: Path,
) -> None:
    make_interactive_project(tmp_path)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    await app.start()

    actor = Actor(51, 52)
    await transport.emit(CommandEvent(actor, 1, "start"))
    await transport.emit(CommandEvent(actor, 2, "start"))

    blocked = Actor(61, 62)
    await app.store.upsert_user("fixture-bot", blocked)
    await app.store.update_user(
        "fixture-bot", blocked.user_id, role="moderator", blocked=True, note="keep"
    )
    messages_before = len(transport.messages)
    await transport.emit(MessageEvent(blocked, 3, "do not store"))

    events = await read_events(tmp_path / "data" / "runtime.sqlite3")
    actor_events = [row for row in events if row["user_id"] == actor.user_id]
    blocked_events = [row for row in events if row["user_id"] == blocked.user_id]
    assert [row["event_type"] for row in actor_events].count("user_first_seen") == 1
    assert {row["event_type"] for row in blocked_events} == {
        "interaction_received",
        "message_received",
    }
    assert len(transport.messages) == messages_before
    managed = next(
        user
        for user in await app.store.list_users("fixture-bot")
        if user.user_id == blocked.user_id
    )
    assert (managed.role, managed.blocked, managed.note) == ("moderator", True, "keep")
    assert "do not store" not in json.dumps(events)
    await app.stop()


@pytest.mark.asyncio
async def test_task_handler_events_have_nullable_actor_and_job_context(
    tmp_path: Path,
) -> None:
    write_handler(
        tmp_path,
        "fixture_bot.handlers.task",
        "from tg_bot_core import HandlerResult, TaskContext\n"
        "async def handle(ctx: TaskContext) -> HandlerResult:\n"
        "    return HandlerResult.success()\n",
    )
    binding = HandlerBinding(
        id="tasks.run",
        module="fixture_bot.handlers.task",
        symbol="handle",
        kind="task",
    )
    writer = CapturingWriter()
    executor = HandlerExecutor(
        HandlerResolver({binding.id: binding}, tmp_path, "fixture_bot"),
        analytics=AnalyticsRecorder("bot", writer),
    )

    result = await executor.execute(
        binding.id,
        "task",
        TaskContext("job-1", {}, {}, logging.getLogger("test.task")),
        metadata={"job_id": "job-1"},
    )

    assert result.outcome_name == "success"
    assert [event.event_type for event in writer.events] == [
        AnalyticsEventType.HANDLER_STARTED,
        AnalyticsEventType.HANDLER_SUCCEEDED,
    ]
    assert all(event.user_id is None and event.chat_id is None for event in writer.events)
    assert all(json.loads(event.metadata_json)["job_id"] == "job-1" for event in writer.events)


@pytest.mark.asyncio
async def test_analytics_failure_is_logged_and_does_not_break_runtime(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    make_interactive_project(tmp_path)
    transport = FakeTransport()
    app = new_app(tmp_path, transport, [])
    await app.start()
    assert app.analytics is not None
    app.analytics._writer = FailingWriter()  # type: ignore[attr-defined]

    with caplog.at_level("ERROR", logger="tg_bot_core.analytics"):
        await transport.emit(CommandEvent(Actor(71, 72), 1, "start"))

    assert transport.messages[-1].text == "Ask True"
    assert any(
        record.message.startswith("Could not record analytics event")
        for record in caplog.records
    )
    session = await app.store.load_session("fixture-bot", Actor(71, 72))
    assert (session.status, session.flow_id, session.state_id) == (
        "active",
        "main",
        "ask",
    )
    await app.stop()
