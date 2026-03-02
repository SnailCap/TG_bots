from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.background.handler_registry import task_handler
from pipubot.background.types.task_types import BackgroundTaskType


@task_handler(BackgroundTaskType.PRINT_HELLO)
async def print_hello(session: AsyncSession, payload: dict) -> None:
    """
    Simple test handler.
    """

    print("👋 HELLO FROM BACKGROUND TASK!")
    print("Payload:", payload)
