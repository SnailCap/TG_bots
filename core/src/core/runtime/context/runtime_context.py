from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeVar, cast

from telegram.ext import Application

from core.runtime.context.bot_data_keys import BotDataKeys

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    app: Application
    keys: BotDataKeys = BotDataKeys()

    def set_services(self, services: Any) -> None:
        self.app.bot_data[self.keys.services] = services

    def get_services(self, expected_type: type[T] | None = None) -> T | Any:
        value = self.app.bot_data[self.keys.services]
        if expected_type is None:
            return value
        return cast(T, value)

    def has_services(self) -> bool:
        return self.keys.services in self.app.bot_data

    def set_engine(self, engine: Any) -> None:
        self.app.bot_data[self.keys.db_engine] = engine

    def get_engine(self) -> Any:
        return self.app.bot_data[self.keys.db_engine]

    def has_engine(self) -> bool:
        return self.keys.db_engine in self.app.bot_data

    def set_session_maker(self, session_maker: Any) -> None:
        self.app.bot_data[self.keys.db_session_maker] = session_maker

    def get_session_maker(self) -> Any:
        return self.app.bot_data[self.keys.db_session_maker]

    def has_session_maker(self) -> bool:
        return self.keys.db_session_maker in self.app.bot_data