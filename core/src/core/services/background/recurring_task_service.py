from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.background.recurring_task_repository import (
    get_recurring_by_key,
    create_recurring_task, disable_recurring_not_in_keys,
)
from core.background.enums import RecurringTaskStatus
from core.shared.utils.time import utc_now


async def ensure_recurring_task(
    session: AsyncSession,
    *,
    key: str,
    task_type: str,
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
        rt.updated_at = utc_now()
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

async def sync_recurring_tasks(
    session: AsyncSession,
    *,
    specs: list[Any],
    prefix: str = "system.",
) -> tuple[int, int]:
    desired_keys = {s.key for s in specs}

    for s in specs:
        await ensure_recurring_task(
            session,
            key=s.key,
            task_type=s.task_type,
            interval_seconds=s.interval_seconds,
            payload_template=s.payload_template,
            first_run_at=s.first_run_at or utc_now(),
            max_runs=s.max_runs,
            status=s.status,
        )

    disabled = await disable_recurring_not_in_keys(
        session,
        prefix=prefix,
        desired_keys=desired_keys,
    )

    return len(specs), disabled