from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from core.interaction.contracts.messenger import Messenger
from core.interaction.input.intents import (
    ServiceCallback,
    ServiceCallbackParser,
    ServiceKind,
)
from core.interaction.input.snapshot import InputSnapshot
from core.interaction.messaging import Responder
from core.interaction.state import InteractionState
from core.interaction.types import ProcessCommand, ServiceCallbackData
from core.interaction.types import UserInputType
from core.interaction.types import UserRole


class UserInput:
    """
    Facade over Telegram Update + PTB Context + DB session + InteractionState.

    Responsibilities:
    - Hold infra objects (update/context/session/messenger/state) and identity snapshot
    - Expose an InputSnapshot for routing
    - Provide thin access to parsed service intent (via ServiceCallbackParser)
    - Provide thin access to message delivery (via Responder)
    """

    def __init__(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        session: AsyncSession,
        *,
        messenger: Messenger,
        state: InteractionState,
        service_parser: ServiceCallbackParser | None = None,
    ) -> None:
        self._update = update
        self._context = context
        self._session = session
        self._messenger = messenger
        self._state = state

        user = update.effective_user
        chat = update.effective_chat
        msg = update.effective_message

        self.telegram_id: int = user.id if user else 0
        self.username: Optional[str] = user.username if user else None
        self.first_name: Optional[str] = user.first_name if user else None
        self.last_name: Optional[str] = user.last_name if user else None

        self.chat_id: int = chat.id if chat else 0
        self.message_id: int = msg.message_id if msg else 0

        # set by identity layer
        self.user_role: UserRole = UserRole.PUBLIC

        self._snapshot: InputSnapshot = InputSnapshot.from_update(update)

        self._service_parser = service_parser or ServiceCallbackParser()
        self._responder = Responder(messenger=messenger, chat_id=self.chat_id, message_id=self.message_id)

        self._service: Optional[ServiceCallback] = None

    # --- infra ---

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

    # --- snapshot passthrough ---

    @property
    def type(self) -> UserInputType:
        return self._snapshot.type

    @property
    def text(self) -> Optional[str]:
        return self._snapshot.text

    @property
    def callback_data(self) -> Optional[str]:
        return self._snapshot.callback_data

    @property
    def is_command(self) -> bool:
        return self._snapshot.is_command

    @property
    def is_callback(self) -> bool:
        return self._snapshot.is_callback

    @property
    def is_message(self) -> bool:
        return self._snapshot.is_message

    @property
    def callback(self) -> str:
        return self._snapshot.callback

    @property
    def command(self) -> Optional[str]:
        return self._snapshot.command

    @property
    def with_send_default(self) -> bool:
        return self._snapshot.with_send_default

    # --- service intent (single source of truth) ---

    @property
    def service(self) -> ServiceCallback:
        if self._service is None:
            self._service = self._service_parser.parse(self._snapshot)
        return self._service

    @property
    def service_kind(self) -> ServiceKind:
        return self.service.kind

    # --- backwards-compatible flags ---

    @property
    def is_service_callback(self) -> bool:
        return self.is_callback and self.callback.startswith(ServiceCallbackData.SVC.value)

    # NAV

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

    # PROCESS START

    @property
    def is_proc_start(self) -> bool:
        return self.service_kind == ServiceKind.PRC_START

    @property
    def proc_key(self) -> Optional[str]:
        return self.service.process_key

    # PROCESS COMMANDS

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

    # --- messaging ---

    async def reply(self, text: str, reply_markup: Any = None, with_send: bool = False):
        return await self._responder.reply(text, reply_markup, with_send=with_send)