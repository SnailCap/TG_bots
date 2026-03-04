from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.background.handler_registry import get_recurring_specs
from core.db.repositories.background.recurring_task_repository import disable_recurring_not_in_keys
from core.services.recurring_task_service import ensure_recurring_task
from core.shared.utils.time_helpers import utcnow

log = logging.getLogger(__name__)

SYSTEM_PREFIX = "system."


def bootstrap_system_recurring(session_maker: async_sessionmaker[AsyncSession]) -> None:
    async def _run() -> None:
        specs = get_recurring_specs(prefix=SYSTEM_PREFIX)
        desired_keys = {s.key for s in specs}

        async with session_maker() as session:
            # 1) ensure all desired tasks exist
            for spec in specs:
                await ensure_recurring_task(
                    session,
                    key=spec.key,
                    task_type=str(spec.task_type),
                    interval_seconds=spec.interval_seconds,
                    payload_template=spec.payload_template,
                    first_run_at=utcnow(),
                    max_runs=spec.max_runs,
                    status=spec.status,
                )

            # 2) disable stale system.* tasks not in registry
            disabled = await disable_recurring_not_in_keys(
                session,
                prefix=SYSTEM_PREFIX,
                desired_keys=desired_keys,
                reason="Removed from registered recurring specs",
            )

            await session.commit()

        log.info(
            "System recurring bootstrap complete: ensured=%d, disabled_stale=%d",
            len(specs),
            disabled,
        )

    asyncio.create_task(_run(), name="bootstrap-system-recurring")