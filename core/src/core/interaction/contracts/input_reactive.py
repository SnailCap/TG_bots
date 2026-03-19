from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.interaction.runtime.user_input import UserInput
from core.interaction.types import UserInputType


class InputReactive(ABC):
    async def handle_input(self, user_input: UserInput) -> Any:
        """
        Main entrypoint to process user input (text, command, callback, etc.)
        """
        if not await self.is_input_valid(user_input):
            await self.handle_unexpected_message(user_input)
            return

        match user_input.type:
            case UserInputType.CALLBACK:
                await self.handle_callback(user_input)
            case UserInputType.MESSAGE:
                await self.handle_message(user_input)
            case _:
                await self.handle_unexpected_message(user_input)

    @abstractmethod
    async def is_input_valid(self, user_input: UserInput) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def handle_callback(self, user_input: UserInput) -> Any:
        raise NotImplementedError

    @abstractmethod
    async def handle_message(self, user_input: UserInput) -> Any:
        raise NotImplementedError

    async def handle_unexpected_message(self, user_input: UserInput) -> Any:
        # дефолт можно оставить здесь
        await user_input.reply("Неожиданное сообщение", None)