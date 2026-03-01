from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import BackgroundTask
from core.enums.background_task_enums import BackgroundTaskStatus, BackgroundTaskType
from core.shared.utils.time_helpers import utcnow


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
        limit: int = 50,
        lease_seconds: int = 120,
) -> list[int]:
    now = now or utcnow()
    lease_until = now + timedelta(seconds=lease_seconds)

    statement = (
        select(BackgroundTask.id)
        .where(
            or_(
                and_(
                    BackgroundTask.status == BackgroundTaskStatus.PENDING,
                    BackgroundTask.run_at <= now,
                ),
                and_(
                    BackgroundTask.status == BackgroundTaskStatus.PROCESSING,
                    BackgroundTask.lease_expires_at.isnot(None),
                    BackgroundTask.lease_expires_at <= now,
                ),
            )
        )
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
            lease_expires_at=lease_until,
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
    Mark the task as DONE.
    """
    ts = finished_at or utcnow()
    await session.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id == task_id)
        .values(
            status=BackgroundTaskStatus.DONE,
            finished_at=ts,
            updated_at=ts,
            lease_expires_at=None,
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
    Mark the task as FAILED (terminal).
    """
    ts = finished_at or utcnow()

    await session.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id == task_id)
        .values(
            status=BackgroundTaskStatus.FAILED,
            finished_at=ts,
            updated_at=ts,
            lease_expires_at=None,
            last_error=error,
            retries=retries,
        )
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
    Put the task back to PENDING with incremented retries and new run_at.

    Worker decides to retry policy (backoff, max retries, etc.).
    """
    await session.execute(
        update(BackgroundTask)
        .where(BackgroundTask.id == task_id)
        .values(
            status=BackgroundTaskStatus.PENDING,
            run_at=run_at,
            retries=retries,
            updated_at=utcnow(),
            started_at=None,
            finished_at=None,
            lease_expires_at=None,
            last_error=error,
        )
    )
