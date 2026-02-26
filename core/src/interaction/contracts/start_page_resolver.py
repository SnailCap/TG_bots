from typing import Protocol

from core.src.interaction.input.user_input import UserInput


class StartPageResolver(Protocol):
    def resolve(self, user_input: UserInput) -> str: ...