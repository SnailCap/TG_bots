from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from core.interaction.contracts.messenger import Messenger


@dataclass(frozen=True, slots=True)
class InputTransport:
    update: Update
    context: ContextTypes.DEFAULT_TYPE
    session: AsyncSession
    messenger: Messenger
    chat_id: int
    message_id: int