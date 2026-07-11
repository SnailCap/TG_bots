from __future__ import annotations

from app.domain.project import BotIdentity
from app.runtime.transport import IncomingUpdate, OutboundMessage, UpdateHandler


class FakeTelegramPort:
    def __init__(self, identity: BotIdentity | None = None) -> None:
        self.identity = identity or BotIdentity(
            bot_id=1001,
            username="studio_test_bot",
            display_name="Studio Test Bot",
        )
        self.messages: list[OutboundMessage] = []
        self.handler: UpdateHandler | None = None
        self.start_count = 0
        self.stop_count = 0
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, handler: UpdateHandler) -> BotIdentity:
        self.handler = handler
        self._running = True
        self.start_count += 1
        return self.identity

    async def stop(self) -> None:
        self._running = False
        self.handler = None
        self.stop_count += 1

    async def send(self, message: OutboundMessage) -> OutboundMessage:
        if not self._running:
            raise RuntimeError("Fake Telegram adapter is not running")
        self.messages.append(message)
        return message

    async def emit(self, update: IncomingUpdate) -> None:
        if not self._running or self.handler is None:
            raise RuntimeError("Fake Telegram adapter is not running")
        await self.handler(update)

