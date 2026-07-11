from typing import Protocol

from ..project import BotIdentity


class BotTokenValidator(Protocol):
    async def validate(self, token: str) -> BotIdentity: ...

