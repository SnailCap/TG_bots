from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest

from tg_bot_core.handlers import HandlerExecutor, HandlerResolver
from tg_bot_core.jobs import DurableJobQueue, JobRuntime
from tg_bot_core.project import HandlerBinding, ScheduleSpec
from tg_bot_core.project.models import ScheduleTrigger
from tg_bot_core.store import SqliteStore

from conftest import make_project, write_handler


async def job_row(database: Path, job_id: str):
    async with aiosqlite.connect(database) as connection:
        connection.row_factory = aiosqlite.Row
        return await (await connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,))).fetchone()


@pytest.mark.asyncio
async def test_durable_queue_claims_retries_completes_and_records_runs(tmp_path: Path) -> None:
    database = tmp_path / "runtime.sqlite3"
    store = SqliteStore(database)
    await store.initialize()
    queue = DurableJobQueue(store, lease_seconds=0.1, retry_base_seconds=0)
    job_id = await queue.enqueue("tasks.example", {"value": 1}, max_attempts=2)

    first = await queue.claim()
    assert first is not None
    assert first.id == job_id
    assert first.handler_id == "tasks.example"
    assert first.payload == {"value": 1}
    await queue.renew_lease(first)
    await queue.fail(first, RuntimeError("temporary"))

    retried = await queue.claim()
    assert retried is not None
    assert retried.id == job_id
    assert retried.attempts == 1
    await queue.complete(retried)

    row = await job_row(database, job_id)
    assert row["status"] == "succeeded"
    assert row["attempts"] == 1
    async with aiosqlite.connect(database) as connection:
        runs = await (await connection.execute(
            "SELECT status FROM job_runs WHERE job_id=? ORDER BY started_at", (job_id,)
        )).fetchall()
    assert [item[0] for item in runs] == ["retrying", "succeeded"]


@pytest.mark.asyncio
async def test_durable_queue_stops_after_max_attempts(tmp_path: Path) -> None:
    database = tmp_path / "runtime.sqlite3"
    store = SqliteStore(database)
    await store.initialize()
    queue = DurableJobQueue(store, retry_base_seconds=0)
    job_id = await queue.enqueue("tasks.always_fails", {}, max_attempts=1)

    job = await queue.claim()
    assert job is not None
    await queue.fail(job, RuntimeError("permanent"))

    assert await queue.claim() is None
    row = await job_row(database, job_id)
    assert row["status"] == "failed"
    assert row["attempts"] == 1
    assert row["last_error"] == "permanent"


@pytest.mark.asyncio
async def test_interval_schedule_materializes_one_durable_task_and_can_be_deactivated(tmp_path: Path) -> None:
    database = tmp_path / "runtime.sqlite3"
    store = SqliteStore(database)
    await store.initialize()
    queue = DurableJobQueue(store)
    schedule = ScheduleSpec(
        id="digest",
        handler="tasks.digest",
        trigger=ScheduleTrigger("interval", 3600),
        payload={"chat_id": 42},
    )

    await queue.sync_schedules({"digest": schedule})
    assert await queue.materialize_due_schedules() == 1
    assert await queue.materialize_due_schedules() == 0
    claimed = await queue.claim()
    assert claimed is not None
    assert claimed.handler_id == "tasks.digest"
    assert claimed.payload == {"chat_id": 42}

    await queue.sync_schedules({})
    async with aiosqlite.connect(database) as connection:
        active = await (await connection.execute("SELECT active FROM schedules WHERE id='digest'" )).fetchone()
    assert active == (0,)


@pytest.mark.asyncio
async def test_job_runtime_invokes_task_handler_and_renews_lease(tmp_path: Path) -> None:
    make_project(tmp_path)
    write_handler(
        tmp_path,
        "fixture_bot.handlers.task",
        """from tg_bot_core import HandlerResult, TaskContext

async def handle(ctx: TaskContext) -> HandlerResult:
    ctx.services["started"].set()
    await ctx.services["release"].wait()
    ctx.services["calls"].append((ctx.job_id, dict(ctx.payload)))
    return HandlerResult.success()
""",
    )
    binding = HandlerBinding(
        id="tasks.run",
        module="fixture_bot.handlers.task",
        symbol="handle",
        kind="task",
    )
    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[tuple[str, dict]] = []
    services = {"started": started, "release": release, "calls": calls}
    executor = HandlerExecutor(
        HandlerResolver({binding.id: binding}, tmp_path, "fixture_bot"),
        services,
    )
    database = tmp_path / "runtime.sqlite3"
    store = SqliteStore(database)
    await store.initialize()
    queue = DurableJobQueue(store, lease_seconds=0.04, retry_base_seconds=0)
    job_id = await queue.enqueue(binding.id, {"value": 7})
    runtime = JobRuntime(queue, executor, services)
    worker = asyncio.create_task(runtime.worker_loop())

    await asyncio.wait_for(started.wait(), timeout=2)
    await asyncio.sleep(0.08)
    competing_queue = DurableJobQueue(store, lease_seconds=0.04)
    assert await competing_queue.claim() is None
    release.set()

    for _ in range(100):
        row = await job_row(database, job_id)
        if row["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    runtime.stop()
    await asyncio.wait_for(worker, timeout=2)

    assert calls == [(job_id, {"value": 7})]
    assert row["status"] == "succeeded"
