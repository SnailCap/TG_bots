from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.src.db.models import BackgroundTask
from core.src.enums.background_task_enums import BackgroundTaskStatus
from core.src.db.repositories.background.background_task_repository import (
    claim_due_task_ids,
    mark_task_done,
    mark_task_failed,
    reschedule_task_for_retry, get_task,
)
from core.src.shared.utils.time_helpers import utcnow

log = logging.getLogger(__name__)


class TaskDispatcher(Protocol):
    async def dispatch(self, session: AsyncSession, task: BackgroundTask) -> None: ...


@dataclass(frozen=True)
class WorkerConfig:
    poll_interval_seconds: float = 1.0
    batch_size: int = 25
    retry_backoff_seconds: int = 30


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
                processed = await self._tick_once()
                if processed == 0:
                    await asyncio.sleep(self._cfg.poll_interval_seconds)
        except asyncio.CancelledError:
            log.info("[worker] cancelled")
            raise
        finally:
            log.info("[worker] stopped")

    async def _tick_once(self) -> int:
        ids = await self._claim_batch()
        if not ids:
            return 0

        processed = 0
        for task_id in ids:
            processed += int(await self._process_one(task_id))
        return processed

    # -------------------------
    # internals
    # -------------------------

    async def _claim_batch(self) -> list[int]:
        now = utcnow()
        async with self._session_maker() as session:
            ids = await claim_due_task_ids(session, now=now, limit=self._cfg.batch_size)
            if not ids:
                return []
            await session.commit()
            return ids

    async def _process_one(self, task_id: int) -> bool:
        async with self._session_maker() as session:
            task = await get_task(session, task_id=task_id)
            if not task:
                return False

            if task.status != BackgroundTaskStatus.PROCESSING:
                return False   

            try:
                await self._dispatcher.dispatch(session, task)
                await self._handle_success(session, task)
                await session.commit()
                return True
            except Exception as exception:
                await self._handle_failure(session, task, exception)
                await session.commit()
                return False

    async def _handle_success(self, session: AsyncSession, task: BackgroundTask) -> None:
        await mark_task_done(session, task_id=task.id, finished_at=utcnow())

    async def _handle_failure(self, session: AsyncSession, task: BackgroundTask, exc: Exception) -> None:
        log.exception("[worker] task failed id=%s type=%s", task.id, task.task_type)

        next_retries = task.retries + 1
        if next_retries <= task.max_retries:
            await reschedule_task_for_retry(
                session,
                task_id=task.id,
                run_at=utcnow() + timedelta(seconds=self._cfg.retry_backoff_seconds),
                retries=next_retries,
                error=str(exc),
            )
        else:
            await mark_task_failed(
                session,
                task_id=task.id,
                error=str(exc),
                retries=next_retries,
                finished_at=utcnow(),
            )
