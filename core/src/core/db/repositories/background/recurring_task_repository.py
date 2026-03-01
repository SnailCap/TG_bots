from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import RecurringTask
from core.enums.background_task_enums import RecurringTaskStatus, BackgroundTaskType
from core.shared.utils.time_helpers import utcnow


# -------------------------
# Create / Get
# -------------------------

async def create_recurring_task(
    session: AsyncSession,
    *,
    key: str,
    task_type: BackgroundTaskType,
    payload_template: dict[str, Any] | None = None,
    first_run_at: datetime | None = None,
    interval_seconds: int,
    max_runs: int | None = None,
    status: RecurringTaskStatus = RecurringTaskStatus.ACTIVE,
) -> RecurringTask:
    """
    Create a RecurringTask row in DB.

    Notes:
    - No transaction control here (no commit/rollback). Caller controls it.
    - next_run_at по умолчанию = first_run_at.
    """
    first = first_run_at or utcnow()
    rt = RecurringTask(
        key=key,
        task_type=task_type,
        status=status,
        first_run_at=first,
        next_run_at=first,
        interval_seconds=interval_seconds,
        max_runs=max_runs,
        payload_template=payload_template or {},
        run_count=0,
        last_run_at=None,
        last_error=None,
    )
    session.add(rt)
    await session.flush()
    return rt


async def get_recurring_task(
    session: AsyncSession,
    *,
    recurring_task_id: int,
) -> RecurringTask | None:
    """
    Get RecurringTask by ID.
    """
    result = await session.execute(
        select(RecurringTask).where(RecurringTask.id == recurring_task_id)
    )
    return result.scalar_one_or_none()


async def get_recurring_by_key(
    session: AsyncSession,
    *,
    key: str,
) -> RecurringTask | None:
    result = await session.execute(
        select(RecurringTask).where(RecurringTask.key == key)
    )
    return result.scalar_one_or_none()


# -------------------------
# Claim (for recurring scheduler)
# -------------------------

async def claim_due_recurring_ids(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 50,
    lease_seconds: int = 120,
) -> list[int]:
    now = now or utcnow()
    lease_until = now + timedelta(seconds=lease_seconds)

    stmt = (
        select(RecurringTask.id)
        .where(
            or_(
                and_(
                    RecurringTask.status == RecurringTaskStatus.ACTIVE,
                    RecurringTask.next_run_at <= now,
                ),
                and_(
                    RecurringTask.status == RecurringTaskStatus.PROCESSING,
                    RecurringTask.lease_expires_at.isnot(None),
                    RecurringTask.lease_expires_at <= now,
                ),
            )
        )
        .order_by(RecurringTask.next_run_at.asc(), RecurringTask.id.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
    )

    result = await session.execute(stmt)
    ids = [row[0] for row in result.all()]
    if not ids:
        return []

    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id.in_(ids))
        .values(
            status=RecurringTaskStatus.PROCESSING,
            lease_expires_at=lease_until,
            updated_at=now,
            last_error=None,
        )
    )
    return ids


# -------------------------
# Status / schedule updates
# -------------------------

async def advance_recurring_schedule(
    session: AsyncSession,
    *,
    recurring_task_id: int,
    last_run_at: datetime | None,
    next_run_at: datetime,
    run_count: int,
    set_active: bool = True,
    disable: bool = False,
    error: str | None = None,
) -> None:
    """
    Update schedule fields after producing BackgroundTask.

    Typical usage:
    - last_run_at = now
    - run_count += 1
    - Next_run_at = old_next_run_at + interval

    If disable=True: set the status to DISABLE.
    If set_active=True: ensure status becomes ACTIVE (useful after PROCESSING claim).
    """
    ts = utcnow()

    # status resolution in one place
    status: RecurringTaskStatus | None
    if disable:
        status = RecurringTaskStatus.DISABLED
    elif set_active:
        status = RecurringTaskStatus.ACTIVE
    else:
        status = None

    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(
            updated_at=ts,
            last_run_at=last_run_at,
            next_run_at=next_run_at,
            run_count=run_count,
            last_error=error,
            lease_expires_at=None,
            **({ "status": status } if status is not None else {}),
        )
    )


async def mark_recurring_error(
    session: AsyncSession,
    *,
    recurring_task_id: int,
    error: str,
    keep_active: bool = True,
) -> None:
    """
    Persist last_error on a recurring row.

    If the row was claimed as PROCESSING, you usually want to return it to ACTIVE;
    otherwise it could get stuck. Keep_active=True does that.
    """
    ts = utcnow()
    status: RecurringTaskStatus | None = RecurringTaskStatus.ACTIVE if keep_active else None

    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(
            updated_at=ts,
            last_error=error,
            lease_expires_at=None,
            **({ "status": status } if status is not None else {}),
        )
    )


async def pause_recurring_task(
    session: AsyncSession,
    *,
    recurring_task_id: int,
) -> None:
    """
    Pause recurring task.
    """
    ts = utcnow()
    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(status=RecurringTaskStatus.PAUSED, updated_at=ts)
    )


async def disable_recurring_task(
    session: AsyncSession,
    *,
    recurring_task_id: int,
) -> None:
    """
    Disable a recurring task.
    """
    ts = utcnow()
    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(status=RecurringTaskStatus.DISABLED, updated_at=ts)
    )