from __future__ import annotations

from typing import Final

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from core.interaction.adapters.ptb.state_store import PtbUserDataStateStore
from core.interaction.contracts.messenger import Messenger
from core.interaction.contracts.session_provider import SessionProvider
from core.interaction.contracts.state_store import StateStore
from core.interaction.runtime.context import InteractionState, UserInput, UserRole
from core.interaction.routing.user_input_router import UserInputRouter
from core.services.identity.contracts import IdentityProvider


class UpdateDispatcher:
    def __init__(
        self,
        *,
        router: UserInputRouter,
        session_provider: SessionProvider,
        identity_provider: IdentityProvider,
        messenger: Messenger,
    ):
        self._router: Final[UserInputRouter] = router
        self._session_provider: Final[SessionProvider] = session_provider
        self._identity_provider: Final[IdentityProvider] = identity_provider
        self._messenger: Final[Messenger] = messenger

    def register_handlers(self, app):
        app.add_handler(CallbackQueryHandler(self.handle_input))
        app.add_handler(MessageHandler(filters.ALL, self.handle_input))

    async def handle_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query is not None:
            try:
                await update.callback_query.answer()
            except TelegramError:
                pass

        async with self._session_provider.session_scope() as session:
            store: StateStore = PtbUserDataStateStore(context.user_data)
            state = InteractionState(store)

            tg_user = update.effective_user

            user = await self._identity_provider.ensure_user(
                session=session,
                telegram_id=tg_user.id if tg_user else 0,
                username=tg_user.username if tg_user else None,
                first_name=tg_user.first_name if tg_user else None,
                last_name=tg_user.last_name if tg_user else None,
            )

            user_input = UserInput(
                update,
                context,
                session=session,
                messenger=self._messenger,
                state=state,
                user_role=UserRole(user.role),
            )

            await self._router.handle_input(user_input)