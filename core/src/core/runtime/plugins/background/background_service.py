from __future__ import annotations

from typing import Protocol


class BackgroundService(Protocol):
    async def run_forever(self) -> None: ...
    def stop(self) -> None: ...