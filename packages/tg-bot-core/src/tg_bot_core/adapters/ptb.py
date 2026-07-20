from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

from ..catalog import CallbackCodec, CatalogError
from ..events import Actor, CallbackEvent, CommandEvent, MessageEvent
from ..transport import BotTransport, EventHandler, OutboundMessage


log = logging.getLogger(__name__)


class PtbTransport(BotTransport):
    def __init__(self, token: str) -> None:
        self._app = Application.builder().token(token).build()
        self._codec = CallbackCodec()
        self._handler: EventHandler | None = None
        self._initialized = False
        self._running = False

    async def start(self, handler: EventHandler) -> None:
        self._handler = handler
        self._app.add_handler(CallbackQueryHandler(self._on_callback))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))
        self._app.add_handler(MessageHandler(filters.COMMAND, self._on_command))
        await self._app.initialize()
        self._initialized = True
        await self._app.start()
        self._running = True
        if self._app.updater is None:
            raise RuntimeError("PTB updater is unavailable.")
        await self._app.updater.start_polling()

    async def stop(self) -> None:
        if self._app.updater and self._running:
            await self._app.updater.stop()
        if self._running:
            await self._app.stop()
            self._running = False
        if self._initialized:
            await self._app.shutdown()
            self._initialized = False

    async def send(self, message: OutboundMessage) -> None:
        keyboard = (
            InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(button.text, callback_data=button.callback_data) for button in row]
                    for row in message.keyboard
                ]
            )
            if message.keyboard
            else None
        )
        await self._app.bot.send_message(
            chat_id=message.chat_id,
            text=message.text,
            reply_markup=keyboard,
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._handler:
            await self._handler(
                MessageEvent(
                    actor=self._actor(update),
                    update_id=update.update_id,
                    text=update.effective_message.text or "",
                )
            )

    async def _on_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._handler:
            return
        raw = update.effective_message.text or ""
        name, _, arguments = raw.partition(" ")
        await self._handler(
            CommandEvent(
                actor=self._actor(update),
                update_id=update.update_id,
                command=name.split("@", 1)[0].removeprefix("/"),
                arguments=arguments,
            )
        )

    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.callback_query:
            await update.callback_query.answer()
        if not self._handler or not update.callback_query:
            return
        try:
            action_id = self._codec.decode(update.callback_query.data or "")
        except (CatalogError, ValueError) as error:
            log.warning("Ignoring invalid callback payload: %s", error)
            return
        await self._handler(
            CallbackEvent(actor=self._actor(update), update_id=update.update_id, action_id=action_id)
        )

    @staticmethod
    def _actor(update: Update) -> Actor:
        user, chat = update.effective_user, update.effective_chat
        if user is None or chat is None:
            raise RuntimeError("Core accepts only updates with a user and chat.")
        return Actor(user.id, chat.id, user.username, user.first_name, user.last_name)
