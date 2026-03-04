from core.interaction.input.user_input import UserInput
from core.interaction import DefaultPageKey


class StartPageResolver:
    def resolve(self, user_input: UserInput) -> str:
        return (
            DefaultPageKey.DEFAULT_ADMIN_HOME
        )