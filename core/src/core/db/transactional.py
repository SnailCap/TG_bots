from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, cast

from sqlalchemy.ext.asyncio import AsyncSession

R = TypeVar("R")


def transactional(func: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
    """
    Wraps an async function into a DB transaction.

    Requirements:
    - Function must receive AsyncSession as a keyword arg `session=...`
      or as the first positional arg after `self` (methods).
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> R:
        session = _extract_session(args, kwargs)

        # If already inside a transaction (nested service call), do nothing special
        if session.in_transaction():
            return await func(*args, **kwargs)

        # Own the transaction scope
        async with session.begin():
            return await func(*args, **kwargs)

    return cast(Callable[..., Awaitable[R]], wrapper)


def _extract_session(args: tuple[Any, ...], kwargs: dict[str, Any]) -> AsyncSession:
    # 1) Preferred: keyword argument
    sess = kwargs.get("session")
    if isinstance(sess, AsyncSession):
        return sess

    # 2) Method style: (self, session, ...)
    if len(args) >= 2 and isinstance(args[1], AsyncSession):
        return args[1]

    # 3) Function style: (session, ...)
    if len(args) >= 1 and isinstance(args[0], AsyncSession):
        return args[0]

    raise TypeError(
        "transactional: AsyncSession not found. "
        "Pass `session=` kwarg or provide session as positional arg."
    )