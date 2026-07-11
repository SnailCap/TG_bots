from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator, Hashable


class SessionLockPool:
    """Serialize updates for one session identity while keeping users concurrent."""

    def __init__(self) -> None:
        self._locks: dict[Hashable, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._references: dict[Hashable, int] = defaultdict(int)
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def acquire(self, key: Hashable) -> AsyncIterator[None]:
        async with self._guard:
            lock = self._locks[key]
            self._references[key] += 1
        try:
            async with lock:
                yield
        finally:
            async with self._guard:
                self._references[key] -= 1
                if self._references[key] <= 0 and not lock.locked():
                    self._references.pop(key, None)
                    self._locks.pop(key, None)

