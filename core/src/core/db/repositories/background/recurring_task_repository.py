from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import RecurringTask
from core.enums.background_task_enums import RecurringTaskStatus
from core.enums.background_task_enums import BackgroundTaskType
from core.shared.utils.time_helpers import utcnow


# Если в enum есть PROCESSING — используем его. Если нет, будем "холдить" next_run_at.
_PROCESSING_STATUS = getattr(RecurringTaskStatus, "PROCESSING", None)
_DISABLED_STATUS = getattr(RecurringTaskStatus, "DISABLED", None) or getattr(RecurringTaskStatus, "DISABLED", None)
_PAUSED_STATUS = getattr(RecurringTaskStatus, "PAUSED", None)


# -------------------------
# Create / Get
# -------------------------

async def create_recurring_task(
        session: AsyncSession,
        *,
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


# -------------------------
# Claim (for recurring scheduler)
# -------------------------

async def claim_due_recurring_ids(
        session: AsyncSession,
        *,
        now: datetime | None = None,
        limit: int = 50,
        claim_hold_seconds: int = 60,
) -> list[int]:
    """
    Claim due ACTIVE recurring tasks and return their IDs.

    Pattern:
    - SELECT ids ... FOR UPDATE SKIP LOCKED
    - UPDATE claimed ids to prevent re-claim

    If RecurringTaskStatus has PROCESSING:
      - set status=PROCESSING
    Else:
      - move next_run_at forward by claim_hold_seconds (temporary hold)
        so other scheduler instances won't immediately pick it up after commit.

    Notes:
    - No commit here. Caller should commit after claiming.
    """
    now = now or utcnow()

    stmt = (
        select(RecurringTask.id)
        .where(RecurringTask.status == RecurringTaskStatus.ACTIVE)
        .where(RecurringTask.next_run_at <= now)
        .order_by(
            RecurringTask.next_run_at.asc(),
            RecurringTask.id.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(limit)
    )
    result = await session.execute(stmt)
    ids = [row[0] for row in result.all()]
    if not ids:
        return []

    values: dict[str, Any] = {
        "updated_at": now,
        "last_error": None,
    }

    if _PROCESSING_STATUS is not None:
        values["status"] = _PROCESSING_STATUS
    else:
        # временно "удерживаем" запись, чтобы избежать повторного claim после commit
        values["next_run_at"] = now + timedelta(seconds=claim_hold_seconds)

    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id.in_(ids))
        .values(**values)
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
    - next_run_at = old_next_run_at + interval

    If disable=True: set status to DISABLED (if exists) else keep current status.
    If set_active=True: ensure status becomes ACTIVE (useful after PROCESSING claim).
    """
    ts = utcnow()
    values: dict[str, Any] = {
        "updated_at": ts,
        "last_run_at": last_run_at,
        "next_run_at": next_run_at,
        "run_count": run_count,
    }
    if error is not None:
        values["last_error"] = error
    else:
        values["last_error"] = None

    if disable:
        if _DISABLED_STATUS is not None:
            values["status"] = _DISABLED_STATUS
    else:
        if set_active:
            values["status"] = RecurringTaskStatus.ACTIVE

    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(**values)
    )


async def mark_recurring_error(
        session: AsyncSession,
        *,
        recurring_task_id: int,
        error: str,
        keep_active: bool = True,
) -> None:
    """
    Persist last_error on recurring row.

    If the row was claimed as PROCESSING, you usually want to return it to ACTIVE,
    otherwise it could get stuck. keep_active=True does that.
    """
    ts = utcnow()
    values: dict[str, Any] = {
        "updated_at": ts,
        "last_error": error,
    }
    if keep_active:
        values["status"] = RecurringTaskStatus.ACTIVE

    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(**values)
    )


async def pause_recurring_task(
        session: AsyncSession,
        *,
        recurring_task_id: int,
) -> None:
    """
    Pause recurring task (if PAUSED exists). Otherwise sets ACTIVE->ACTIVE no-op.
    """
    if _PAUSED_STATUS is None:
        return

    ts = utcnow()
    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(status=_PAUSED_STATUS, updated_at=ts)
    )


async def disable_recurring_task(
        session: AsyncSession,
        *,
        recurring_task_id: int,
) -> None:
    """
    Disable recurring task (if DISABLED exists). If not, falls back to PAUSED if exists.
    """
    ts = utcnow()
    status = _DISABLED_STATUS or _PAUSED_STATUS
    if status is None:
        return

    await session.execute(
        update(RecurringTask)
        .where(RecurringTask.id == recurring_task_id)
        .values(status=status, updated_at=ts)
    )
