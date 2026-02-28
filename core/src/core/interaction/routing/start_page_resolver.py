from __future__ import annotations

from core.interaction.input.user_input import UserInput
from core.interaction.types import DefaultPageKey, UserRole


class DefaultStartPageResolver:
    def resolve(self, user_input: UserInput) -> str:
        return (
            DefaultPageKey.DEFAULT_ADMIN_HOME
            if user_input.user_role == UserRole.ADMIN
            else DefaultPageKey.DEFAULT_PUBLIC_HOME
        )
