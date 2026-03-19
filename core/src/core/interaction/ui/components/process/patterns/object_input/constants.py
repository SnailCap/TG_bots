from __future__ import annotations

from enum import StrEnum


OBJECT_DATA_KEY = "object_data"
ERRORS_KEY = "errors"

DEFAULT_ERROR_TEXT_KEY = "error"

DEFAULT_CALLBACK_EDIT = "edit"
DEFAULT_CALLBACK_CONFIRM = "confirm"


class InputFlowMode(StrEnum):
    INPUT_ONLY = "input_only"
    INPUT_CONFIRM = "input_confirm"
    EDIT_ONLY = "edit_only"
    EDIT_CONFIRM = "edit_confirm"