from __future__ import annotations

from typing import Callable

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """
    Create async SQLAlchemy engine.
    Core must NOT read env here — caller passes database_url.
    """
    return create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
    )


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Returns a factory that creates AsyncSession.
    """
    maker = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return maker
