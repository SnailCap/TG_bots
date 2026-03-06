# core/background/recurring_scheduler_worker.py

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.db.transactional import transactional
from core.services.background.background_task_service import enqueue_background_task
from core.shared.utils.time import utc_now
from core.db.repositories.background.recurring_task_repository import (
    claim_due_recurring_ids,
    get_recurring_task,
    advance_recurring_schedule,
    mark_recurring_error,
)
from core.background.enums import RecurringTaskStatus

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecurringSchedulerConfig:
    poll_interval_seconds: float = 1.0
    batch_size: int = 50
    claim_lease_seconds: int = 120

    tick_throttle_seconds: float = 0.1

    skip_missed_runs: bool = True


class RecurringSchedulerWorker:
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
                else:
                    await asyncio.sleep(self._cfg.tick_throttle_seconds)
        finally:
            log.info("[recurring] stopped")

    async def _tick_once(self) -> int:
        now = utc_now()
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
            try:
                return await self._produce_one_tx(session, recurring_id=recurring_id)
            except Exception as exc:
                # ВАЖНО: мы тут уже ВНЕ транзакции (или транзакция откатилась),
                # поэтому можно отдельной транзакцией записать ошибку.
                try:
                    await self._mark_error_tx(session, recurring_id=recurring_id, exc=exc)
                except Exception:
                    log.exception("[recurring] failed to persist recurring error recurring_id=%s", recurring_id)
                return False

    @transactional
    async def _produce_one_tx(self, session: AsyncSession, *, recurring_id: int) -> bool:
        rt = await get_recurring_task(session, recurring_task_id=recurring_id)
        if not rt or rt.status != RecurringTaskStatus.PROCESSING:
            return False

        now = utc_now()
        interval = timedelta(seconds=rt.interval_seconds)

        run_at = rt.next_run_at
        if run_at is None:
            run_at = now
        else:
            run_at = max(run_at, now)

        payload = dict(rt.payload_template or {})

        await enqueue_background_task(
            session,
            task_type=rt.task_type,
            payload=payload,
            run_at=run_at,
            source="recurring",
            recurring_task_id=rt.id,
        )

        if rt.next_run_at is None:
            next_run = now + interval
        elif self._cfg.skip_missed_runs and rt.next_run_at <= now:
            next_run = now + interval
        else:
            next_run = rt.next_run_at + interval

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

        # commit НЕ нужен: @transactional сделает commit сам
        return True

    @transactional
    async def _mark_error_tx(self, session: AsyncSession, *, recurring_id: int, exc: Exception) -> None:
        await mark_recurring_error(session, recurring_task_id=recurring_id, error=str(exc), keep_active=True)