from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.src.db.models import BackgroundTask
from core.src.enums.background_task_enums import BackgroundTaskStatus, BackgroundTaskType
from core.src.shared.utils.time_helpers import utcnow


# -------------------------
# Create
# -------------------------

async def create_task(
        session: AsyncSession,
        *,
        task_type: BackgroundTaskType,
        payload: dict[str, Any],
        run_at: datetime | None = None,
        priority: int = 0,
        max_retries: int = 5,
        status: BackgroundTaskStatus = BackgroundTaskStatus.PENDING,
        recurring_task_id: int | None = None,
) -> BackgroundTask:
    """
    Create a BackgroundTask row in DB.

    Notes:
    - No transaction control here (no commit/rollback). Caller controls it.
    - Returns ORM object with PK populated after flush.
    """
    task = BackgroundTask(
        task_type=task_type,
        status=status,
        run_at=run_at or utcnow(),
        payload=payload,
        priority=priority,
        max_retries=max_retries,
        recurring_task_id=recurring_task_id,
    )
    session.add(task)
    await session.flush()
    return task


async def get_task(
        session: AsyncSession,
        *,
        task_id: int,
) -> BackgroundTask | None:
    """
    Get BackgroundTask by ID.

    Notes:
    - No transaction control here.
    - Returns ORM object or None if not found.
    """
    result = await session.execute(
        select(BackgroundTask).where(BackgroundTask.id == task_id)
    )
    return result.scalar_one_or_none()


# -------------------------
# Claim (for worker)
# -------------------------

async def claim_due_task_ids(
        session: AsyncSession,
        *,
        now: datetime | None = None,
        limit: int = 25,
) -> list[int]:
    """
    Claim (lock + mark as PROCESSING) due PENDING tasks and return their IDs.

    Pattern:
    - SELECT ids ... FOR UPDATE SKIP LOCKED
    - UPDATE claimed ids -> PROCESSING + started_at + updated_at

    Notes:
    - No commit here. Worker should commit after claiming.
    - SKIP LOCKED makes it safe to run multiple workers later.
    """
    now = now or utcnow()

    statement = (
        select(BackgroundTask.id)
        .where(BackgroundTask.status == BackgroundTaskStatus.PENDING)
        .where(BackgroundTask.run_at <= now)
        .order_by(
            BackgroundTask.priority.desc(),
            BackgroundTask.run_at.asc(),
            BackgroundTask.id.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
    result = await session.execute(statement)
    ids = [row[0] for row in result.all()]
    if not ids:
        return []

    await session.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id.in_(ids))
        .values(
            status=BackgroundTaskStatus.PROCESSING,
            started_at=now,
            updated_at=now,
            last_error=None,
        )
    )

    return ids


# -------------------------
# Status updates
# -------------------------

async def mark_task_done(
        session: AsyncSession,
        *,
        task_id: int,
        finished_at: datetime | None = None,
) -> None:
    """
    Mark task as DONE.
    """
    ts = finished_at or utcnow()
    await session.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id == task_id)
        .values(
            status=BackgroundTaskStatus.DONE,
            finished_at=ts,
            updated_at=ts,
        )
    )


async def mark_task_failed(
        session: AsyncSession,
        *,
        task_id: int,
        error: str | None = None,
        finished_at: datetime | None = None,
        retries: int | None = None,
) -> None:
    """
    Mark task as FAILED (terminal).
    """
    ts = finished_at or utcnow()
    values: dict[str, Any] = {
        "status": BackgroundTaskStatus.FAILED,
        "finished_at": ts,
        "updated_at": ts,
    }
    if error is not None:
        values["last_error"] = error
    if retries is not None:
        values["retries"] = retries

    await session.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id == task_id)
        .values(**values)
    )


async def reschedule_task_for_retry(
        session: AsyncSession,
        *,
        task_id: int,
        run_at: datetime,
        retries: int,
        error: str | None = None,
) -> None:
    """
    Put task back to PENDING with incremented retries and new run_at.

    Worker decides retry policy (backoff, max retries, etc.).
    """
    values: dict[str, Any] = {
        "status": BackgroundTaskStatus.PENDING,
        "run_at": run_at,
        "retries": retries,
        "updated_at": utcnow(),
        "started_at": None,
        "finished_at": None,
    }
    if error is not None:
        values["last_error"] = error

    await session.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id == task_id)
        .values(**values)
    )
