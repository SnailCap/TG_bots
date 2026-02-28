from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.interaction.types import ProcessCommand, ServiceCallbackData
from core.interaction.input.snapshot import InputSnapshot


class ServiceKind(str, Enum):
    NONE = "none"
    NAV = "nav"
    NAV_TO = "nav_to"
    PRC_START = "prc_start"
    PRC_CMD = "prc_cmd"


@dataclass(frozen=True, slots=True)
class ServiceCallback:
    kind: ServiceKind
    raw: str
    nav_target: Optional[str] = None
    process_key: Optional[str] = None
    process_cmd: Optional[ProcessCommand] = None


class ServiceCallbackParser:
    """
    Parse callback_data that follows our framework protocol: `svc:*`.

    All 'svc:*' semantics live here, not in UserInput.
    """

    def parse(self, snapshot: InputSnapshot) -> ServiceCallback:
        cb = snapshot.callback
        if not (snapshot.is_callback and cb.startswith(ServiceCallbackData.SVC.value)):
            return ServiceCallback(kind=ServiceKind.NONE, raw=cb)

        # NAV: exact commands first
        if cb == ServiceCallbackData.NAV_PREVIOUS.value:
            return ServiceCallback(kind=ServiceKind.NAV, raw=cb)
        if cb == ServiceCallbackData.NAV_CURRENT.value:
            return ServiceCallback(kind=ServiceKind.NAV, raw=cb)
        if cb == ServiceCallbackData.NAV_HOME.value:
            return ServiceCallback(kind=ServiceKind.NAV, raw=cb)

        # NAV_TO
        if cb.startswith(ServiceCallbackData.NAV_TO.value):
            target = cb.removeprefix(ServiceCallbackData.NAV_TO.value).strip() or None
            return ServiceCallback(kind=ServiceKind.NAV_TO, raw=cb, nav_target=target)

        # PRC_START
        if cb.startswith(ServiceCallbackData.PRC_START.value):
            key = cb.removeprefix(ServiceCallbackData.PRC_START.value).strip() or None
            return ServiceCallback(kind=ServiceKind.PRC_START, raw=cb, process_key=key)

        # PRC_CMD
        if cb.startswith(ServiceCallbackData.PRC_CMD.value):
            raw_cmd = cb.removeprefix(ServiceCallbackData.PRC_CMD.value).strip()
            try:
                cmd = ProcessCommand(raw_cmd) if raw_cmd else None
            except ValueError:
                cmd = None
            return ServiceCallback(kind=ServiceKind.PRC_CMD, raw=cb, process_cmd=cmd)

        # Unknown svc namespace (still svc:* but not supported here)
        return ServiceCallback(kind=ServiceKind.NONE, raw=cb)