from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.services.background.recurring_task_service import ensure_recurring_task
from core.shared.utils.time_helpers import utcnow

from pipubot.background.jobs.recurring_registry import SYSTEM_RECURRING_SPECS

log = logging.getLogger(__name__)


def bootstrap_system_recurring(session_maker: async_sessionmaker[AsyncSession]) -> None:
    """
    One-time bootstrap. Applies SYSTEM_RECURRING_SPECS idempotently.
    """

    async def _run() -> None:
        async with session_maker() as session:
            for spec in SYSTEM_RECURRING_SPECS:
                await ensure_recurring_task(
                    session,
                    key=spec.key,
                    task_type=spec.task_type,
                    interval_seconds=spec.interval_seconds,
                    payload_template=spec.payload_template,
                    first_run_at=spec.first_run_at or utcnow(),
                    max_runs=spec.max_runs,
                    status=spec.status,
                )
            await session.commit()

        log.info("Bootstrapped %d system recurring task(s).", len(SYSTEM_RECURRING_SPECS))

    asyncio.create_task(_run(), name="bootstrap-system-recurring")