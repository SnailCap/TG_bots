from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, TypeVar, cast


ActionFunction = TypeVar("ActionFunction", bound=Callable[..., Any])
ACTION_NAME_ATTRIBUTE = "__botstudio_action_name__"
_ACTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,127}$")


def action(name: str) -> Callable[[ActionFunction], ActionFunction]:
    normalized = name.strip()
    if not _ACTION_NAME.fullmatch(normalized):
        raise ValueError(
            "Action name must start with a letter or underscore and contain only "
            "letters, digits, underscore, dot or dash"
        )

    def decorator(function: ActionFunction) -> ActionFunction:
        setattr(function, ACTION_NAME_ATTRIBUTE, normalized)
        return function

    return decorator


def get_action_name(function: Callable[..., Any]) -> str | None:
    value = getattr(function, ACTION_NAME_ATTRIBUTE, None)
    return cast(str | None, value)

