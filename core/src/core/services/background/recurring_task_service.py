from __future__ import annotations

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.background.recurring_task_repository import (
    get_recurring_by_key,
    create_recurring_task,
)
from core.enums.background_task_enums import BackgroundTaskType, RecurringTaskStatus
from core.shared.utils.time_helpers import utcnow


async def ensure_recurring_task(
    session: AsyncSession,
    *,
    key: str,
    task_type: BackgroundTaskType,
    interval_seconds: int,
    payload_template: dict | None = None,
    first_run_at: datetime | None = None,
    max_runs: int | None = None,
    status: RecurringTaskStatus = RecurringTaskStatus.ACTIVE,
) -> None:
    rt = await get_recurring_by_key(session, key=key)
    if rt:
        rt.task_type = task_type
        rt.interval_seconds = interval_seconds
        rt.payload_template = payload_template or {}
        rt.max_runs = max_runs
        rt.status = status
        rt.updated_at = utcnow()
        return

    await create_recurring_task(
        session,
        key=key,
        task_type=task_type,
        payload_template=payload_template,
        first_run_at=first_run_at,
        interval_seconds=interval_seconds,
        max_runs=max_runs,
        status=status,
    )