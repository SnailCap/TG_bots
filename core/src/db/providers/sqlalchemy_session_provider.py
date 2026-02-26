from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from core.src.interaction.contracts.session_provider import SessionProvider


class SqlAlchemySessionProvider:
    """
    Universal SQLAlchemy session provider with transaction scope.
    Works for Controller and background workers.
    """

    def __init__(self, session_maker: Callable[[], AsyncSession]) -> None:
        self._session_maker = session_maker

    @asynccontextmanager
    async def session_scope(self) -> AsyncIterator[AsyncSession]:
        async with self._session_maker() as session:
            async with session.begin():
                yield session
