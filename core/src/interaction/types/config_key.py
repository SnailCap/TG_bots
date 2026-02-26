from enum import Enum


class ButtonConfigKey(str, Enum):
    TEXT = "text"
    CALLBACK_DATA = "callback_data"
    LINK = "link"


class RenderableConfigKey(str, Enum):
    TEXT = "text"
    KEYBOARD_LAYOUT = "keyboard_layout"


class PageConfigKey(str, Enum):
    ACCESS_LEVEL = "access_level"
