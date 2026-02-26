from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from core.src.interaction.contracts.messenger import Messenger
from core.src.interaction.state import InteractionState
from core.src.interaction.types import ProcessCommand, ServiceCallbackData
from core.src.interaction.types.user_input_type import UserInputType
from core.src.interaction.types.user_role import UserRole


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


class UserInput:
    """
    Facade over Telegram Update + PTB Context + DB session + InteractionState.

    Goals:
    - Keep update/context/session available (backwards compatible).
    - Provide parsed snapshot fields (type/text/callback_data).
    - Centralize parsing of callback_data into intent-level flags.
    - Avoid magic strings: rely on enums (ServiceCallbackData / ProcessCommand).
    """

    def __init__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession,
        *,
        messenger: Messenger,
        state: InteractionState,
    ) -> None:
        self._update = update
        self._context = context
        self._session: AsyncSession = session
        self._messenger = messenger
        self._state: InteractionState = state

        # identity snapshot (safe)
        user = update.effective_user
        chat = update.effective_chat
        msg = update.effective_message

        self.telegram_id: int = user.id if user else 0
        self.username: Optional[str] = user.username if user else None
        self.first_name: Optional[str] = user.first_name if user else None
        self.last_name: Optional[str] = user.last_name if user else None

        self.chat_id: int = chat.id if chat else 0
        self.message_id: int = msg.message_id if msg else 0

        self.user_role: UserRole = UserRole.PUBLIC

        # input (parsed snapshot)
        self.type: UserInputType = UserInputType.UNKNOWN
        self.text: Optional[str] = None
        self.callback_data: Optional[str] = None

        self._parse_input_from_update()

        # Cached parsed service callback (single source of truth)
        self._service: Optional[ServiceCallback] = None

    # -------------------------
    # Backwards-compatible access
    # -------------------------

    @property
    def update(self) -> Update:
        return self._update

    @property
    def context(self) -> ContextTypes.DEFAULT_TYPE:
        return self._context

    @property
    def session(self) -> AsyncSession:
        return self._session

    @property
    def messenger(self) -> Messenger:
        return self._messenger

    @property
    def state(self) -> InteractionState:
        return self._state

    # -------------------------
    # Parsing (private)
    # -------------------------

    def _parse_input_from_update(self) -> None:
        if self._update.callback_query is not None:
            self._parse_callback()
            return

        if self._update.message is not None:
            self._parse_message(self._update.message.text)
            return

        self.type = UserInputType.UNKNOWN
        self.text = None
        self.callback_data = None

    def _parse_callback(self) -> None:
        self.type = UserInputType.CALLBACK
        self.callback_data = self._update.callback_query.data or ""
        self.text = None

    def _parse_message(self, raw_text: Optional[str]) -> None:
        if not raw_text:
            self.type = UserInputType.MESSAGE
            self.text = None
            self.callback_data = None
            return

        if raw_text.startswith("/"):
            self.type = UserInputType.COMMAND
            self.text = raw_text[1:]
            self.callback_data = None
            return

        self.type = UserInputType.MESSAGE
        self.text = raw_text
        self.callback_data = None

    # -------------------------
    # Kind flags
    # -------------------------

    @property
    def is_command(self) -> bool:
        return self.type == UserInputType.COMMAND

    @property
    def is_callback(self) -> bool:
        return self.type == UserInputType.CALLBACK

    @property
    def is_message(self) -> bool:
        return self.type == UserInputType.MESSAGE

    # -------------------------
    # Convenience values
    # -------------------------

    @property
    def callback(self) -> str:
        """Callback data as non-null string."""
        return self.callback_data or ""

    @property
    def command(self) -> Optional[str]:
        """Command name (without '/') if this input is a command, else None."""
        return self.text if self.is_command else None

    @property
    def with_send_default(self) -> bool:
        """
        Default render strategy:
        - CALLBACK -> edit a bot message
        - MESSAGE/COMMAND -> send a new bot message
        """
        return not self.is_callback

    # -------------------------
    # Service callback parsing (single source of truth)
    # -------------------------

    def _parse_service_callback(self) -> ServiceCallback:
        cb = self.callback
        if not (self.is_callback and cb.startswith(ServiceCallbackData.SVC.value)):
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
            cmd: ProcessCommand | None
            try:
                cmd = ProcessCommand(raw_cmd) if raw_cmd else None
            except ValueError:
                cmd = None
            return ServiceCallback(kind=ServiceKind.PRC_CMD, raw=cb, process_cmd=cmd)

        # Unknown svc namespace (still svc:* but not supported here)
        return ServiceCallback(kind=ServiceKind.NONE, raw=cb)

    @property
    def service(self) -> ServiceCallback:
        if self._service is None:
            self._service = self._parse_service_callback()
        return self._service

    @property
    def service_kind(self) -> ServiceKind:
        return self.service.kind

    # -------------------------
    # Service flags (backwards compatible wrappers)
    # -------------------------

    @property
    def is_service_callback(self) -> bool:
        return self.is_callback and self.callback.startswith(ServiceCallbackData.SVC.value)

    # --- NAV ---

    @property
    def is_nav_callback(self) -> bool:
        return self.service_kind in (ServiceKind.NAV, ServiceKind.NAV_TO)

    @property
    def is_nav_previous(self) -> bool:
        return self.callback == ServiceCallbackData.NAV_PREVIOUS.value

    @property
    def is_nav_current(self) -> bool:
        return self.callback == ServiceCallbackData.NAV_CURRENT.value

    @property
    def is_nav_home(self) -> bool:
        return self.callback == ServiceCallbackData.NAV_HOME.value

    @property
    def is_nav_to(self) -> bool:
        return self.service_kind == ServiceKind.NAV_TO

    @property
    def nav_target(self) -> Optional[str]:
        return self.service.nav_target

    # --- PROCESS START ---

    @property
    def is_proc_start(self) -> bool:
        return self.service_kind == ServiceKind.PRC_START

    @property
    def proc_key(self) -> Optional[str]:
        return self.service.process_key

    # --- PROCESS COMMANDS ---

    @property
    def is_proc_cmd(self) -> bool:
        return self.service_kind == ServiceKind.PRC_CMD

    @property
    def proc_cmd(self) -> ProcessCommand | None:
        return self.service.process_cmd

    @property
    def is_proc_next(self) -> bool:
        return self.proc_cmd == ProcessCommand.NEXT

    @property
    def is_proc_prev(self) -> bool:
        return self.proc_cmd == ProcessCommand.PREV

    @property
    def is_proc_cancel(self) -> bool:
        return self.proc_cmd == ProcessCommand.CANCEL

    # -------------------------
    # Messaging
    # -------------------------

    async def reply(self, text: str, reply_markup=None, with_send: bool = False):
        """
        Reply facade:
        - with_send=True -> always sends a new message
        - with_send=False -> send_or_edit using current message_id
        """
        if with_send:
            return await self._messenger.send(
                chat_id=self.chat_id,
                text=text,
                reply_markup=reply_markup,
            )

        return await self._messenger.send_or_edit(
            chat_id=self.chat_id,
            message_id=self.message_id,
            text=text,
            reply_markup=reply_markup,
        )