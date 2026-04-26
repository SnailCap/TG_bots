from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from core.interaction.contracts.messenger import Messenger

from .actor import InputActor
from .callback import CallbackInput
from .callback_parser import ServiceCallbackParser, ServiceKind
from .enums import UserRole
from .message import MessageInput
from .reply import ReplyPort
from .state import InteractionState
from .transport import InputTransport


class UserInput:
    """
    Aggregate root of the current interaction context.

    Responsibilities:
    - compose an actor / transport / message / callback / state / reply
    - keep the public API compact and grouped
    - Preserve a small compatibility surface for old router/page/process code
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
        user_role: UserRole = UserRole.PUBLIC,
    ) -> None:
        user = update.effective_user
        chat = update.effective_chat
        msg = update.effective_message

        self.transport = InputTransport(
            update=update,
            context=context,
            session=session,
            messenger=messenger,
            chat_id=chat.id if chat else 0,
            message_id=msg.message_id if msg else 0,
        )

        self.actor = InputActor(
            telegram_id=user.id if user else 0,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
            role=user_role,
        )

        self.message = MessageInput.from_update(update)
        self._callback = CallbackInput(
            message=self.message,
            parser=service_parser or ServiceCallbackParser(),
        )
        self.state = state
        self.reply_port = ReplyPort(
            messenger=messenger,
            chat_id=self.transport.chat_id,
            message_id=self.transport.message_id,
        )

    # -----------------------------
    # Grouped API
    # -----------------------------

    @property
    def update(self) -> Update:
        return self.transport.update

    @property
    def context(self) -> ContextTypes.DEFAULT_TYPE:
        return self.transport.context

    @property
    def session(self) -> AsyncSession:
        return self.transport.session

    @property
    def messenger(self) -> Messenger:
        return self.transport.messenger

    @property
    def callback_input(self) -> CallbackInput:
        return self._callback

    # -----------------------------
    # Actor passthrough
    # -----------------------------

    @property
    def telegram_id(self) -> int:
        return self.actor.telegram_id

    @property
    def username(self) -> str | None:
        return self.actor.username

    @property
    def first_name(self) -> str | None:
        return self.actor.first_name

    @property
    def last_name(self) -> str | None:
        return self.actor.last_name

    @property
    def user_role(self) -> UserRole:
        return self.actor.role

    @property
    def chat_id(self) -> int:
        return self.transport.chat_id

    @property
    def message_id(self) -> int:
        return self.transport.message_id

    # -----------------------------
    # Backwards-compatible message API
    # -----------------------------

    @property
    def type(self):
        return self.message.type

    @property
    def text(self) -> str | None:
        return self.message.text

    @property
    def callback_data(self) -> str | None:
        return self.message.callback_data

    @property
    def callback_raw(self) -> str:
        return self.message.callback

    @property
    def callback_str(self) -> str:
        return self.message.callback

    @property
    def callback_value(self) -> str:
        return self.message.callback

    @property
    def command(self) -> str | None:
        return self.message.command

    @property
    def with_send_default(self) -> bool:
        return self.message.with_send_default

    @property
    def is_command(self) -> bool:
        return self.message.is_command

    @property
    def is_callback(self) -> bool:
        return self.message.is_callback

    @property
    def is_message(self) -> bool:
        return self.message.is_message

    @property
    def callback(self) -> str:
        # legacy/raw callback string
        return self.message.callback

    # -----------------------------
    # Backwards-compatible callback/service API
    # -----------------------------

    @property
    def service(self):
        return self._callback.service

    @property
    def service_kind(self) -> ServiceKind:
        return self._callback.service_kind

    @property
    def nav_kind(self):
        return self._callback.nav_kind

    @property
    def is_service_callback(self) -> bool:
        return self._callback.is_service

    @property
    def is_nav_callback(self) -> bool:
        return self._callback.is_nav

    @property
    def is_nav_home(self) -> bool:
        return self._callback.is_nav_home

    @property
    def is_nav_current(self) -> bool:
        return self._callback.is_nav_current

    @property
    def is_nav_previous(self) -> bool:
        return self._callback.is_nav_previous

    @property
    def is_nav_to(self) -> bool:
        return self._callback.is_nav_to

    @property
    def nav_target(self) -> str | None:
        return self._callback.nav_target

    @property
    def is_proc_start(self) -> bool:
        return self._callback.is_proc_start

    @property
    def proc_key(self) -> str | None:
        return self._callback.proc_key

    @property
    def is_proc_cmd(self) -> bool:
        return self._callback.is_proc_cmd

    @property
    def proc_cmd(self):
        return self._callback.proc_cmd

    @property
    def is_proc_next(self) -> bool:
        return self._callback.is_proc_next

    @property
    def is_proc_prev(self) -> bool:
        return self._callback.is_proc_prev

    @property
    def is_proc_cancel(self) -> bool:
        return self._callback.is_proc_cancel

    @property
    def step_callback(self) -> str | None:
        return self._callback.step_callback

    @property
    def step_callback_payload(self) -> str | None:
        return self._callback.step_callback_payload

    # -----------------------------
    # Messaging
    # -----------------------------

    async def reply(self, text: str, reply_markup=None, with_send: bool = False):
        return await self.reply_port.reply(text, reply_markup, with_send=with_send)