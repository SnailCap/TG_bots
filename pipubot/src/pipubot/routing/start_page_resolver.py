from core.interaction.runtime.context.user_input import UserInput
from core.interaction.types import DefaultPageKey


class StartPageResolver:
    def resolve(self, user_input: UserInput) -> str:
        return (
            DefaultPageKey.DEFAULT_ADMIN_HOME
        )