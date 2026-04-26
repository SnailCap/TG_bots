from __future__ import annotations

from core.interaction.runtime.context.user_input import UserInput


class HelperStartPageResolver:
    def resolve(self, user_input: UserInput) -> str:  # noqa: ARG002
        return "helper_home"
