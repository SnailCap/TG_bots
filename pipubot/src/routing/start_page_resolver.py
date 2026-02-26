from core.src.interaction.input.user_input import UserInput
from core.src.interaction.types import DefaultPageKey


class StartPageResolver:
    def resolve(self, user_input: UserInput) -> str:
        return (
            DefaultPageKey.DEFAULT_ADMIN_HOME
        )