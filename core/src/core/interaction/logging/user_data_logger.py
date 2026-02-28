import json
from contextlib import AbstractAsyncContextManager

from core.interaction.input.user_input import UserInput
from core.interaction.logging.logging_flags import LoggingFlag


class UserDataLogger(AbstractAsyncContextManager):
    def __init__(self, user_input: UserInput, label: str = ""):
        self.user_input = user_input
        self.label = label
        self.enabled = LoggingFlag.ENABLE_USER_DATA_LOGGING

    async def __aenter__(self):
        if self.enabled:
            print(f"\n 🟢 USER DATA BEFORE {self.label}:")
            self._print_data()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.enabled:
            print(f"\n 🔴 USER DATA AFTER {self.label}:")
            self._print_data()
            print("\n" + "-" * 60 + "\n")

    def _print_data(self):
        data = self.user_input.state.dump()
        print(json.dumps(data, indent=2, ensure_ascii=False))

