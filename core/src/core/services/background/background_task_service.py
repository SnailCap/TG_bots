from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.repositories.background.background_task_repository import create_task
from core.shared.utils.time import utc_now


async def enqueue_background_task(
    session: AsyncSession,
    *,
    task_type: str,
    payload: dict[str, Any] | None = None,
    run_at: datetime | None = None,
    source: str = "manual",
    recurring_task_id: int | None = None,
) -> None:
    """
    High-level orchestration wrapper over create_task().

    Responsibilities:
    - sets _source in payload
    - defaults run_at to utc_now()
    - keeps repository layer clean (SQL only)
    """

    p = dict(payload or {})
    p.setdefault("_source", source)

    await create_task(
        session,
        task_type=task_type,
        run_at=run_at or utc_now(),
        payload=p,
        recurring_task_id=recurring_task_id,
    )