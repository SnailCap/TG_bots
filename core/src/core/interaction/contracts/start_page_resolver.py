from typing import Protocol

from core.interaction.runtime.user_input import UserInput


class StartPageResolver(Protocol):
    def resolve(self, user_input: UserInput) -> str: ...
