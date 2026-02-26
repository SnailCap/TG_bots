from enum import Enum


class BotCommand(str, Enum):
    START_COMMAND = "start"
    HOME_COMMAND = "home"
