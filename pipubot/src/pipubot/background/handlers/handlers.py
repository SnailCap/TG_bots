from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from pipubot.background.task_types import PipubotTaskType

log = logging.getLogger(__name__)

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]


async def print_hello(session: AsyncSession, payload: dict[str, Any]) -> None:
    message = payload.get("message", "Hello from background task 👋")
    print(message)
    log.info("[task] PRINT_HELLO executed: %s", message)


def build_task_handlers() -> dict[str, Handler]:
    return {
        str(PipubotTaskType.PRINT_HELLO): print_hello,
    }