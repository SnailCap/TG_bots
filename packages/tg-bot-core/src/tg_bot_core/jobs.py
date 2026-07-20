from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import uuid4

import aiosqlite

from .handlers import HandlerExecutor
from .project import ScheduleSpec
from .sdk import TaskContext
from .store import SqliteStore, to_timestamp, utc_now

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    id: str
    handler_id: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


class DurableJobQueue:
    def __init__(self, store: SqliteStore, *, lease_seconds: float = 60, retry_base_seconds: float = 5) -> None:
        self._store = store
        self._lease_seconds = lease_seconds
        self._retry_base_seconds = retry_base_seconds

    async def sync_schedules(self, schedules: Mapping[str, ScheduleSpec]) -> None:
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            await connection.execute("UPDATE schedules SET active=0, updated_at=?", (to_timestamp(now),))
            for schedule in schedules.values():
                if schedule.trigger.type != "interval" or schedule.trigger.seconds is None:
                    continue
                await connection.execute(
                    """INSERT INTO schedules (id, handler_id, payload_json, interval_seconds, next_run_at, active, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT(id) DO UPDATE SET handler_id=excluded.handler_id,
                    payload_json=excluded.payload_json, interval_seconds=excluded.interval_seconds,
                    active=1, updated_at=excluded.updated_at""",
                    (
                        schedule.id,
                        schedule.handler,
                        json.dumps(dict(schedule.payload), ensure_ascii=False, allow_nan=False),
                        schedule.trigger.seconds,
                        to_timestamp(now),
                        to_timestamp(now),
                    ),
                )
            await connection.commit()

    async def enqueue(
        self,
        handler_id: str,
        payload: Mapping[str, Any],
        *,
        delay_seconds: float = 0,
        max_attempts: int = 5,
    ) -> str:
        job_id = str(uuid4())
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            await connection.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, 'queued', 0, ?, NULL, NULL, ?, ?)",
                (
                    job_id,
                    handler_id,
                    json.dumps(dict(payload), ensure_ascii=False, allow_nan=False),
                    to_timestamp(now + timedelta(seconds=delay_seconds)),
                    max_attempts,
                    to_timestamp(now),
                    to_timestamp(now),
                ),
            )
            await connection.commit()
        return job_id

    async def materialize_due_schedules(self) -> int:
        now = utc_now()
        created = 0
        async with aiosqlite.connect(self._store.path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("BEGIN IMMEDIATE")
            rows = await (
                await connection.execute(
                    "SELECT * FROM schedules WHERE active=1 AND next_run_at<=?", (to_timestamp(now),)
                )
            ).fetchall()
            for row in rows:
                await connection.execute(
                    "INSERT INTO jobs VALUES (?, ?, ?, ?, 'queued', 0, 5, NULL, NULL, ?, ?)",
                    (
                        str(uuid4()),
                        row["handler_id"],
                        row["payload_json"],
                        to_timestamp(now),
                        to_timestamp(now),
                        to_timestamp(now),
                    ),
                )
                next_run = row["next_run_at"]
                while next_run <= to_timestamp(now):
                    next_run += row["interval_seconds"]
                await connection.execute(
                    "UPDATE schedules SET next_run_at=?, updated_at=? WHERE id=?",
                    (next_run, to_timestamp(now), row["id"]),
                )
                created += 1
            await connection.commit()
        return created

    async def claim(self) -> ClaimedJob | None:
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            connection.row_factory = aiosqlite.Row
            await connection.execute("BEGIN IMMEDIATE")
            row = await (
                await connection.execute(
                    """SELECT * FROM jobs
                    WHERE (status IN ('queued', 'retrying') AND run_at<=?)
                       OR (status='processing' AND lease_until<=?)
                    ORDER BY run_at LIMIT 1""",
                    (to_timestamp(now), to_timestamp(now)),
                )
            ).fetchone()
            if row is None:
                await connection.commit()
                return None
            await connection.execute(
                "UPDATE jobs SET status='processing', lease_until=?, updated_at=? WHERE id=?",
                (to_timestamp(now + timedelta(seconds=self._lease_seconds)), to_timestamp(now), row["id"]),
            )
            await connection.execute(
                "INSERT INTO job_runs VALUES (?, ?, ?, NULL, 'processing', NULL)",
                (str(uuid4()), row["id"], to_timestamp(now)),
            )
            await connection.commit()
        return ClaimedJob(
            row["id"], row["handler_id"], json.loads(row["payload_json"]), row["attempts"], row["max_attempts"]
        )

    async def complete(self, job: ClaimedJob) -> None:
        now = utc_now()
        async with aiosqlite.connect(self._store.path) as connection:
            await connection.execute(
                "UPDATE jobs SET status='succeeded', lease_until=NULL, updated_at=? WHERE id=?",
                (to_timestamp(now), job.id),
            )
            await connection.execute(
                "UPDATE job_runs SET status='succeeded', finished_at=? WHERE job_id=? AND status='processing'",
                (to_timestamp(now), job.id),
            )
            await connection.commit()

    async def renew_lease(self, job: ClaimedJob) -> None:
        now = utc_now()
        # Very short leases are useful in tests, but a heartbeat still needs a
        # small scheduling/SQLite jitter budget after it confirms ownership.
        renewal_window = max(self._lease_seconds, 0.25)
        async with aiosqlite.connect(self._store.path) as connection:
            result = await connection.execute(
                "UPDATE jobs SET lease_until=?, updated_at=? WHERE id=? AND status='processing'",
                (to_timestamp(now + timedelta(seconds=renewal_window)), to_timestamp(now), job.id),
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
                """UPDATE jobs SET status=?, attempts=?, run_at=?, lease_until=NULL,
                last_error=?, updated_at=? WHERE id=?""",
                (
                    status,
                    attempts,
                    to_timestamp(now if terminal else now + timedelta(seconds=delay)),
                    str(error),
                    to_timestamp(now),
                    job.id,
                ),
            )
            await connection.execute(
                "UPDATE job_runs SET status=?, finished_at=?, error=? WHERE job_id=? AND status='processing'",
                (status, to_timestamp(now), str(error), job.id),
            )
            await connection.commit()


class JobRuntime:
    def __init__(
        self,
        queue: DurableJobQueue,
        executor: HandlerExecutor,
        services: Mapping[str, Any],
    ) -> None:
        self._queue = queue
        self._executor = executor
        self._services = services
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
            lease_task: asyncio.Task[None] | None = None
            try:
                await self._queue.renew_lease(job)
                lease_task = asyncio.create_task(self._renew_lease_until_done(job))
                context = TaskContext(job.id, job.payload, self._services, logging.getLogger(f"task.{job.handler_id}"))
                result = await self._executor.execute(
                    job.handler_id,
                    "task",
                    context,
                    metadata={"job_id": job.id},
                )
                if result.outcome_name != "success":
                    raise RuntimeError(
                        f"Task handler '{job.handler_id}' returned non-success outcome '{result.outcome_name}'."
                    )
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
        while True:
            await self._queue.renew_lease(job)
            await asyncio.sleep(self._queue.lease_renew_interval)

    async def _wait_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            return
