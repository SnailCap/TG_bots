from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import AsyncIterator

from app.domain.runtime import RuntimeEvent


class InMemoryEventBus:
    def __init__(self, *, capacity: int = 2_000, subscriber_capacity: int = 500) -> None:
        self._events: deque[RuntimeEvent] = deque(maxlen=max(1, capacity))
        self._subscriber_capacity = max(1, subscriber_capacity)
        self._subscribers: set[asyncio.Queue[RuntimeEvent]] = set()
        self._next_id = 1
        self._lock = asyncio.Lock()

    async def publish(self, event: RuntimeEvent) -> RuntimeEvent:
        async with self._lock:
            stored = replace(event, id=self._next_id)
            self._next_id += 1
            self._events.append(stored)
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(stored)
        return stored

    def snapshot(
        self,
        *,
        project_id: str | None = None,
        after_id: int = 0,
        limit: int = 500,
    ) -> tuple[RuntimeEvent, ...]:
        bounded = min(max(1, limit), 2_000)
        values = [
            event
            for event in self._events
            if event.id > after_id
            and (project_id is None or event.project_id in {None, project_id})
        ]
        return tuple(values[-bounded:])

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[RuntimeEvent]]:
        queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue(
            maxsize=self._subscriber_capacity
        )
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

