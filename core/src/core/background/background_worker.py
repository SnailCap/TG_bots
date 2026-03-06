from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.background.errors import NonRetryableTaskError
from core.db.models import BackgroundTask
from core.db.transactional import transactional
from core.background.enums import BackgroundTaskStatus
from core.db.repositories.background.background_task_repository import (
    claim_due_task_ids,
    mark_task_done,
    mark_task_failed,
    reschedule_task_for_retry,
    get_task,
    renew_task_lease,
)
from core.shared.utils.time import utc_now

log = logging.getLogger(__name__)


class TaskDispatcher(Protocol):
    async def dispatch(self, session: AsyncSession, task: BackgroundTask) -> None: ...


@dataclass(frozen=True)
class WorkerConfig:
    poll_interval_seconds: float = 1.0
    batch_size: int = 25
    claim_lease_seconds: int = 120

    lease_renew_interval_seconds: float = 40.0

    max_concurrency: int = 10
    retry_base_seconds: int = 10
    retry_max_seconds: int = 15 * 60
    retry_jitter_seconds: int = 5


class BackgroundWorker:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        dispatcher: TaskDispatcher,
        config: WorkerConfig | None = None,
    ) -> None:
        self._session_maker = session_maker
        self._dispatcher = dispatcher
        self._cfg = config or WorkerConfig()
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run_forever(self) -> None:
        log.info("[worker] started")
        try:
            while not self._stop_event.is_set():
                try:
                    processed = await self._tick_once()
                except asyncio.CancelledError:
                    log.info("[worker] cancelled")
                    raise
                except Exception:
                    log.exception("[worker] tick crashed (worker will continue)")
                    processed = 0

                if processed == 0:
                    await asyncio.sleep(self._cfg.poll_interval_seconds)
        finally:
            log.info("[worker] stopped")

    async def _tick_once(self) -> int:
        ids = await self._claim_batch()
        if not ids:
            return 0

        sem = asyncio.Semaphore(self._cfg.max_concurrency)

        async def run_one(tid: int) -> bool:
            async with sem:
                return await self._process_one(tid)

        results = await asyncio.gather(*(run_one(tid) for tid in ids), return_exceptions=True)

        ok = 0
        for r in results:
            if isinstance(r, Exception):
                log.exception("[worker] task runner crashed", exc_info=r)
            elif r:
                ok += 1

        return ok

    async def _claim_batch(self) -> list[int]:
        async with self._session_maker() as session:
            return await self._claim_batch_tx(session)

    @transactional
    async def _claim_batch_tx(self, session: AsyncSession) -> list[int]:
        now = utc_now()
        ids = await claim_due_task_ids(
            session,
            now=now,
            limit=self._cfg.batch_size,
            lease_seconds=self._cfg.claim_lease_seconds,
        )
        return ids or []

    async def _process_one(self, task_id: int) -> bool:
        stop = asyncio.Event()
        hb_task: asyncio.Task | None = None

        if self._cfg.lease_renew_interval_seconds > 0:
            hb_task = asyncio.create_task(self._lease_heartbeat(task_id, stop))

        try:
            async with self._session_maker() as session:
                return await self._process_one_tx(session, task_id=task_id)
        finally:
            stop.set()
            if hb_task:
                hb_task.cancel()
                try:
                    await hb_task
                except Exception:
                    pass

    @transactional
    async def _process_one_tx(self, session: AsyncSession, *, task_id: int) -> bool:
        task = await get_task(session, task_id=task_id)
        if not task:
            return False

        if task.status != BackgroundTaskStatus.PROCESSING:
            return False

        try:
            await self._dispatcher.dispatch(session, task)
            await mark_task_done(session, task_id=task.id, finished_at=utc_now())
            return True

        except Exception as exc:
            await self._handle_failure(session, task, exc)
            return False

    async def _lease_heartbeat(self, task_id: int, stop: asyncio.Event) -> None:
        interval = self._cfg.lease_renew_interval_seconds
        try:
            while not stop.is_set():
                await asyncio.sleep(interval)

                async with self._session_maker() as session:
                    updated = await self._renew_lease_tx(session, task_id=task_id)

                if updated == 0:
                    return

        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[worker] lease heartbeat failed task_id=%s", task_id)

    @transactional
    async def _renew_lease_tx(self, session: AsyncSession, *, task_id: int) -> int:
        return await renew_task_lease(
            session,
            task_id=task_id,
            lease_seconds=self._cfg.claim_lease_seconds,
        )

    def _calc_backoff(self, retries: int) -> int:
        base = self._cfg.retry_base_seconds * (2 ** (retries - 1))
        base = min(base, self._cfg.retry_max_seconds)
        jitter = random.randint(0, self._cfg.retry_jitter_seconds)
        return base + jitter

    async def _handle_failure(self, session: AsyncSession, task: BackgroundTask, exc: Exception) -> None:
        log.exception("[worker] task failed id=%s type=%s", task.id, task.task_type)

        next_retries = task.retries + 1

        if isinstance(exc, NonRetryableTaskError):
            await mark_task_failed(
                session,
                task_id=task.id,
                error=str(exc),
                retries=next_retries,
                finished_at=utc_now(),
            )
            return

        if next_retries <= task.max_retries:
            delay = self._calc_backoff(next_retries)
            await reschedule_task_for_retry(
                session,
                task_id=task.id,
                run_at=utc_now() + timedelta(seconds=delay),
                retries=next_retries,
                error=str(exc),
            )
        else:
            await mark_task_failed(
                session,
                task_id=task.id,
                error=str(exc),
                retries=next_retries,
                finished_at=utc_now(),
            )