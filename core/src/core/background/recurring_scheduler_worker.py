import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.shared.utils.time_helpers import utcnow
from core.db.repositories.background.recurring_task_repository import (
    claim_due_recurring_ids,
    get_recurring_task,
    advance_recurring_schedule,
    mark_recurring_error,
)
from core.db.repositories.background.background_task_repository import create_task  # если нет — добавьте repo-функцию
from core.enums.background_task_enums import RecurringTaskStatus

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class RecurringSchedulerConfig:
    poll_interval_seconds: float = 1.0
    batch_size: int = 50
    claim_lease_seconds: int = 120

class RecurringSchedulerService:
    def __init__(self, session_maker: async_sessionmaker[AsyncSession], cfg: RecurringSchedulerConfig | None = None):
        self._session_maker = session_maker
        self._cfg = cfg or RecurringSchedulerConfig()
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run_forever(self) -> None:
        log.info("[recurring] started")
        try:
            while not self._stop_event.is_set():
                n = await self._tick_once()
                if n == 0:
                    await asyncio.sleep(self._cfg.poll_interval_seconds)
        finally:
            log.info("[recurring] stopped")

    async def _tick_once(self) -> int:
        now = utcnow()
        async with self._session_maker() as session:
            ids = await claim_due_recurring_ids(
                session,
                now=now,
                limit=self._cfg.batch_size,
                lease_seconds=self._cfg.claim_lease_seconds,
            )
            if not ids:
                return 0
            await session.commit()

        produced = 0
        for rid in ids:
            produced += int(await self._produce_one(rid))
        return produced

    async def _produce_one(self, recurring_id: int) -> bool:
        async with self._session_maker() as session:
            rt = await get_recurring_task(session, recurring_task_id=recurring_id)
            if not rt or rt.status != RecurringTaskStatus.PROCESSING:
                return False

            try:
                now = utcnow()

                # 1) create a background task (linked)
                await create_task(
                    session,
                    task_type=rt.task_type,
                    run_at=rt.next_run_at,  # или now, если “просрочено”
                    payload=rt.payload_template,
                    recurring_task_id=rt.id,
                )

                # 2) advance schedule (no drift)
                next_run = rt.next_run_at + timedelta(seconds=rt.interval_seconds)
                next_count = rt.run_count + 1

                disable = (rt.max_runs is not None) and (next_count >= rt.max_runs)

                await advance_recurring_schedule(
                    session,
                    recurring_task_id=rt.id,
                    last_run_at=now,
                    next_run_at=next_run,
                    run_count=next_count,
                    set_active=True,
                    disable=disable,
                    error=None,
                )

                await session.commit()
                return True

            except Exception as exc:
                await mark_recurring_error(session, recurring_task_id=recurring_id, error=str(exc), keep_active=True)
                await session.commit()
                return False