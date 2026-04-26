from __future__ import annotations

from dataclasses import dataclass

from .callback_parser import NavKind, ServiceCallback, ServiceCallbackParser, ServiceKind
from .callback_protocol import ServiceCallbackData
from .commands import ProcessCommand
from .message import MessageInput


@dataclass(frozen=True, slots=True)
class NavCallbackView:
    kind: NavKind | None
    target: str | None

    @property
    def exists(self) -> bool:
        return self.kind is not None

    @property
    def is_home(self) -> bool:
        return self.kind == NavKind.HOME

    @property
    def is_current(self) -> bool:
        return self.kind == NavKind.CURRENT

    @property
    def is_previous(self) -> bool:
        return self.kind == NavKind.PREVIOUS

    @property
    def is_target(self) -> bool:
        return self.kind == NavKind.TARGET


@dataclass(frozen=True, slots=True)
class ProcessCallbackView:
    kind: ServiceKind
    key: str | None
    cmd: ProcessCommand | None

    @property
    def is_start(self) -> bool:
        return self.kind == ServiceKind.PRC_START

    @property
    def is_command(self) -> bool:
        return self.kind == ServiceKind.PRC_CMD

    @property
    def is_next(self) -> bool:
        return self.cmd == ProcessCommand.NEXT

    @property
    def is_prev(self) -> bool:
        return self.cmd == ProcessCommand.PREV

    @property
    def is_cancel(self) -> bool:
        return self.cmd == ProcessCommand.CANCEL


class CallbackInput:
    """
    Callback semantics wrapper.

    Knows:
    - raw callback string
    - parsed service intent
    - step payload normalization

    Does NOT know:
    - routing
    - UI rendering
    - process/page behavior
    """

    def __init__(
        self,
        *,
        message: MessageInput,
        parser: ServiceCallbackParser | None = None,
    ) -> None:
        self._message = message
        self._parser = parser or ServiceCallbackParser()
        self._service: ServiceCallback | None = None

    @property
    def raw(self) -> str:
        return self._message.callback

    @property
    def exists(self) -> bool:
        return self._message.is_callback and bool(self.raw)

    @property
    def service(self) -> ServiceCallback:
        if self._service is None:
            self._service = self._parser.parse(self._message)
        return self._service

    @property
    def service_kind(self) -> ServiceKind:
        return self.service.kind

    @property
    def is_service(self) -> bool:
        return self._message.is_callback and self.raw.startswith(ServiceCallbackData.SVC.value)

    @property
    def is_step(self) -> bool:
        return self._message.is_callback and self.raw.startswith(ServiceCallbackData.ST.value)

    @property
    def is_nav(self) -> bool:
        return self.service_kind == ServiceKind.NAV

    @property
    def is_process_start(self) -> bool:
        return self.service_kind == ServiceKind.PRC_START

    @property
    def is_process_command(self) -> bool:
        return self.service_kind == ServiceKind.PRC_CMD

    @property
    def nav(self) -> NavCallbackView:
        return NavCallbackView(
            kind=self.service.nav_kind,
            target=self.service.nav_target,
        )

    @property
    def process(self) -> ProcessCallbackView:
        return ProcessCallbackView(
            kind=self.service_kind,
            key=self.service.process_key,
            cmd=self.service.process_cmd,
        )

    @property
    def step_callback(self) -> str | None:
        """
        Normalized callback payload for step-level business handlers.

        Examples:
        - "st:confirm_add_student:create" -> "confirm_add_student:create"
        - "confirm_add_student:create" -> "confirm_add_student:create"
        """
        if not self.exists:
            return None

        raw = self.raw
        if not raw:
            return None

        prefix = ServiceCallbackData.ST.value
        if raw.startswith(prefix):
            return raw[len(prefix):]

        return raw

    @property
    def step_callback_payload(self) -> str | None:
        """
        Payload for step-level custom callbacks.

        Examples:
        - recognized svc:* callback -> raw callback unchanged
        - unknown svc:* callback -> strips leading 'svc:'
        - st:* callback -> raw callback unchanged here
        - plain callback -> raw callback unchanged
        """
        if not self.exists:
            return None

        raw = self.raw
        if not raw:
            return None

        if self.service_kind is not ServiceKind.NONE:
            return raw

        svc_prefix = ServiceCallbackData.SVC.value
        if raw.startswith(svc_prefix):
            return raw[len(svc_prefix):]

        return raw

    # -----------------------------
    # Backwards-compatible flat API
    # -----------------------------

    @property
    def nav_kind(self) -> NavKind | None:
        return self.service.nav_kind

    @property
    def nav_target(self) -> str | None:
        return self.service.nav_target

    @property
    def proc_key(self) -> str | None:
        return self.service.process_key

    @property
    def proc_cmd(self) -> ProcessCommand | None:
        return self.service.process_cmd

    @property
    def is_nav_home(self) -> bool:
        return self.nav.is_home

    @property
    def is_nav_current(self) -> bool:
        return self.nav.is_current

    @property
    def is_nav_previous(self) -> bool:
        return self.nav.is_previous

    @property
    def is_nav_to(self) -> bool:
        return self.nav.is_target

    @property
    def is_proc_start(self) -> bool:
        return self.process.is_start

    @property
    def is_proc_cmd(self) -> bool:
        return self.process.is_command

    @property
    def is_proc_next(self) -> bool:
        return self.process.is_next

    @property
    def is_proc_prev(self) -> bool:
        return self.process.is_prev

    @property
    def is_proc_cancel(self) -> bool:
        return self.process.is_cancel