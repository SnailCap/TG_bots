from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import uuid4

import aiosqlite

from .store import SqliteStore, to_timestamp, utc_now

log = logging.getLogger(__name__)
TaskHandler = Callable[["TaskContext", dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ScheduleSpec:
    id: str
    task_name: str
    interval_seconds: float
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not self.task_name or self.interval_seconds <= 0:
            raise ValueError("Schedule id/task name and a positive interval are required.")


@dataclass(frozen=True, slots=True)
class TaskContext:
    services: Mapping[str, Any]
    job_id: str


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: str
    task_name: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


class DurableJobQueue:
    def __init__(self, store: SqliteStore, *, lease_seconds: float = 60, retry_base_seconds: float = 5) -> None:
        self._store = store
        self._lease_seconds = lease_seconds
        self._retry_base_seconds = retry_base_seconds

    async def sync_schedules(self, schedules: tuple[ScheduleSpec, ...] | list[ScheduleSpec]) -> None:
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            await connection.execute("UPDATE schedules SET active=0, updated_at=?", (to_timestamp(now),))
            for schedule in schedules:
                await connection.execute(
                    """INSERT INTO schedules (id, task_name, payload_json, interval_seconds, next_run_at, active, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(id) DO UPDATE SET task_name=excluded.task_name, payload_json=excluded.payload_json,
                    interval_seconds=excluded.interval_seconds, active=1, updated_at=excluded.updated_at""",
                    (schedule.id, schedule.task_name, json.dumps(dict(schedule.payload or {})), schedule.interval_seconds, to_timestamp(now), to_timestamp(now)),
                )
            await connection.commit()

    async def enqueue(self, task_name: str, payload: Mapping[str, Any], *, delay_seconds: float = 0, max_attempts: int = 5) -> str:
        job_id = str(uuid4())
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            await connection.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, 'queued', 0, ?, NULL, NULL, ?, ?)",
                (job_id, task_name, json.dumps(dict(payload)), to_timestamp(now + timedelta(seconds=delay_seconds)), max_attempts, to_timestamp(now), to_timestamp(now)),
            )
            await connection.commit()
        return job_id

    async def materialize_due_schedules(self) -> int:
        now = utc_now()
        created = 0
        async with aiosqlite.connect(self._store.path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("BEGIN IMMEDIATE")
            rows = await (await connection.execute("SELECT * FROM schedules WHERE active=1 AND next_run_at<=?", (to_timestamp(now),))).fetchall()
            for row in rows:
                job_id = str(uuid4())
                await connection.execute(
                    "INSERT INTO jobs VALUES (?, ?, ?, ?, 'queued', 0, 5, NULL, NULL, ?, ?)",
                    (job_id, row["task_name"], row["payload_json"], to_timestamp(now), to_timestamp(now), to_timestamp(now)),
                )
                await connection.execute("UPDATE schedules SET next_run_at=?, updated_at=? WHERE id=?", (row["next_run_at"] + row["interval_seconds"], to_timestamp(now), row["id"]))
                created += 1
            await connection.commit()
        return created

    async def claim(self) -> ClaimedJob | None:
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("BEGIN IMMEDIATE")
            row = await (await connection.execute(
                """SELECT * FROM jobs WHERE (status IN ('queued', 'retrying') AND run_at<=?) OR (status='processing' AND lease_until<=?)
                ORDER BY run_at LIMIT 1""", (to_timestamp(now), to_timestamp(now)),
            )).fetchone()
            if row is None:
                await connection.commit()
                return None
            lease_until = to_timestamp(now + timedelta(seconds=self._lease_seconds))
            await connection.execute("UPDATE jobs SET status='processing', lease_until=?, updated_at=? WHERE id=?", (lease_until, to_timestamp(now), row["id"]))
            await connection.execute("INSERT INTO job_runs VALUES (?, ?, ?, NULL, 'processing', NULL)", (str(uuid4()), row["id"], to_timestamp(now)))
            await connection.commit()
        return ClaimedJob(row["id"], row["task_name"], json.loads(row["payload_json"]), row["attempts"], row["max_attempts"])

    async def complete(self, job: ClaimedJob) -> None:
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            await connection.execute("UPDATE jobs SET status='succeeded', lease_until=NULL, updated_at=? WHERE id=?", (to_timestamp(now), job.id))
            await connection.execute("UPDATE job_runs SET status='succeeded', finished_at=? WHERE job_id=? AND status='processing'", (to_timestamp(now), job.id))
            await connection.commit()

    async def renew_lease(self, job: ClaimedJob) -> None:
        """Keep a claimed job exclusive while its handler is still running."""
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            result = await connection.execute(
                "UPDATE jobs SET lease_until=?, updated_at=? WHERE id=? AND status='processing'",
                (to_timestamp(now + timedelta(seconds=self._lease_seconds)), to_timestamp(now), job.id),
            )
            if result.rowcount != 1:
                raise RuntimeError(f"Cannot renew lease for job '{job.id}'.")
            await connection.commit()

    @property
    def lease_renew_interval(self) -> float:
        return max(0.01, min(1.0, self._lease_seconds / 2))

    async def fail(self, job: ClaimedJob, error: Exception) -> None:
        now = utc_now()
        attempts = job.attempts + 1
        terminal = attempts >= job.max_attempts
        status = "failed" if terminal else "retrying"
        delay = min(self._retry_base_seconds * (2 ** max(0, attempts - 1)), 900)
        async with aiosqlite.connect(self._store.path) as connection:
            await connection.execute(
                "UPDATE jobs SET status=?, attempts=?, run_at=?, lease_until=NULL, last_error=?, updated_at=? WHERE id=?",
                (status, attempts, to_timestamp(now if terminal else now + timedelta(seconds=delay)), str(error), to_timestamp(now), job.id),
            )
            await connection.execute("UPDATE job_runs SET status=?, finished_at=?, error=? WHERE job_id=? AND status='processing'", (status, to_timestamp(now), str(error), job.id))
            await connection.commit()


class JobRuntime:
    def __init__(self, queue: DurableJobQueue, handlers: Mapping[str, TaskHandler], services: Mapping[str, Any]) -> None:
        self._queue, self._handlers, self._services = queue, dict(handlers), services
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def scheduler_loop(self) -> None:
        while not self._stop.is_set():
            await self._queue.materialize_due_schedules()
            await self._wait_or_stop(1)

    async def worker_loop(self) -> None:
        while not self._stop.is_set():
            job = await self._queue.claim()
            if job is None:
                await self._wait_or_stop(0.25)
                continue
            handler = self._handlers.get(job.task_name)
            lease_task: asyncio.Task[None] | None = None
            try:
                if handler is None:
                    raise RuntimeError(f"No task handler registered for '{job.task_name}'.")
                lease_task = asyncio.create_task(self._renew_lease_until_done(job))
                await handler(TaskContext(self._services, job.id), job.payload)
            except Exception as error:
                log.exception("Job %s failed", job.id)
                await self._queue.fail(job, error)
            else:
                await self._queue.complete(job)
            finally:
                if lease_task is not None:
                    lease_task.cancel()
                    await asyncio.gather(lease_task, return_exceptions=True)

    async def _renew_lease_until_done(self, job: ClaimedJob) -> None:
        # Stopping only prevents new claims. A handler already in progress must
        # retain its lease until it completes or the supervisor times out.
        while True:
            await asyncio.sleep(self._queue.lease_renew_interval)
            await self._queue.renew_lease(job)

    async def _wait_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            return
