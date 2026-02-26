from typing import Protocol
from contextlib import asynccontextmanager
from typing import AsyncIterator, Any


class SessionProvider(Protocol):
    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[Any]:
        ...