from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .callback_protocol import ServiceCallbackData
from .commands import ProcessCommand
from .message import MessageInput


class ServiceKind(str, Enum):
    NONE = "none"
    NAV = "nav"
    PRC_START = "prc_start"
    PRC_CMD = "prc_cmd"


class NavKind(str, Enum):
    HOME = "home"
    CURRENT = "current"
    PREVIOUS = "previous"
    TARGET = "target"


@dataclass(frozen=True, slots=True)
class ServiceCallback:
    kind: ServiceKind
    raw: str

    nav_kind: Optional[NavKind] = None
    nav_target: Optional[str] = None

    process_key: Optional[str] = None
    process_cmd: Optional[ProcessCommand] = None


class ServiceCallbackParser:
    """
    Parse callback_data that follows the public framework protocol.

    Supported infrastructure callbacks:
    - svc:nav:<target>
    - svc:prc:start:<process_key>
    - svc:prc:cmd:<command>

    All 'svc:*' semantics live here, not in UserInput.
    """

    def parse(self, message: MessageInput) -> ServiceCallback:
        cb = message.callback
        if not (message.is_callback and cb.startswith(ServiceCallbackData.SVC.value)):
            return ServiceCallback(kind=ServiceKind.NONE, raw=cb)

        nav_prefix = ServiceCallbackData.NAV.value
        if cb.startswith(nav_prefix):
            target = cb.removeprefix(nav_prefix).strip()

            if target == "home":
                return ServiceCallback(
                    kind=ServiceKind.NAV,
                    raw=cb,
                    nav_kind=NavKind.HOME,
                )

            if target == "current":
                return ServiceCallback(
                    kind=ServiceKind.NAV,
                    raw=cb,
                    nav_kind=NavKind.CURRENT,
                )

            if target == "previous":
                return ServiceCallback(
                    kind=ServiceKind.NAV,
                    raw=cb,
                    nav_kind=NavKind.PREVIOUS,
                )

            return ServiceCallback(
                kind=ServiceKind.NAV,
                raw=cb,
                nav_kind=NavKind.TARGET,
                nav_target=target or None,
            )

        if cb.startswith(ServiceCallbackData.PRC_START.value):
            key = cb.removeprefix(ServiceCallbackData.PRC_START.value).strip() or None
            return ServiceCallback(
                kind=ServiceKind.PRC_START,
                raw=cb,
                process_key=key,
            )

        if cb.startswith(ServiceCallbackData.PRC_CMD.value):
            raw_cmd = cb.removeprefix(ServiceCallbackData.PRC_CMD.value).strip()
            try:
                cmd = ProcessCommand(raw_cmd) if raw_cmd else None
            except ValueError:
                cmd = None

            return ServiceCallback(
                kind=ServiceKind.PRC_CMD,
                raw=cb,
                process_cmd=cmd,
            )

        return ServiceCallback(kind=ServiceKind.NONE, raw=cb)