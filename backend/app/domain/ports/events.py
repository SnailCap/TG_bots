from typing import Protocol

from ..runtime import RuntimeEvent


class EventPublisher(Protocol):
    async def publish(self, event: RuntimeEvent) -> RuntimeEvent: ...

