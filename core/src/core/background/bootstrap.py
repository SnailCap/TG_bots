from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.background.handler_registry import get_recurring_specs
from core.db.repositories.background.recurring_task_repository import disable_recurring_not_in_keys
from core.services.background.recurring_task_service import ensure_recurring_task
from core.shared.utils.time import utc_now

log = logging.getLogger(__name__)


def bootstrap_registered_recurring(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    prefix: str = "system.",
) -> None:
    async def _run() -> None:
        specs = get_recurring_specs(prefix=prefix)
        desired_keys = {s.key for s in specs}

        async with session_maker() as session:
            for spec in specs:
                await ensure_recurring_task(
                    session,
                    key=spec.key,
                    task_type=spec.task_type,
                    interval_seconds=spec.interval_seconds,
                    payload_template=spec.payload_template,
                    first_run_at=utc_now(),
                    max_runs=spec.max_runs,
                    status=spec.status,
                )

            disabled = await disable_recurring_not_in_keys(
                session,
                prefix=prefix,
                desired_keys=desired_keys,
                reason="Removed from registered recurring specs",
            )

            await session.commit()

        log.info(
            "Recurring bootstrap complete: prefix=%s ensured=%d disabled_stale=%d",
            prefix,
            len(specs),
            disabled,
        )

    asyncio.create_task(_run(), name="bootstrap-registered-recurring")