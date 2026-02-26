from __future__ import annotations
from typing import Protocol, Any


class AppPlugin(Protocol):
    async def start(self, app: Any) -> None: ...
    async def stop(self) -> None: ...
