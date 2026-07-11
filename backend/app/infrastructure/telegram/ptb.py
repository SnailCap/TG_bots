from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton as PtbKeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.domain.project import BotIdentity
from app.runtime.transport import (
    IncomingUpdate,
    Keyboard,
    KeyboardKind,
    MediaKind,
    OutboundMessage,
    UpdateHandler,
    UpdateKind,
)

log = logging.getLogger(__name__)

UpdateErrorHandler = Callable[[Exception, IncomingUpdate | None], Awaitable[None]]


class PtbLongPollingAdapter:
    """python-telegram-bot 22.x long-polling implementation of TelegramPort."""

    def __init__(
        self,
        token: str,
        *,
        private_chats_only: bool = True,
        drop_pending_updates: bool = False,
        error_handler: UpdateErrorHandler | None = None,
    ) -> None:
        self._token = token
        self._private_chats_only = private_chats_only
        self._drop_pending_updates = drop_pending_updates
        self._error_handler = error_handler
        self._application: Application | None = None
        self._handler: UpdateHandler | None = None
        self._running = False
        self._lifecycle_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, handler: UpdateHandler) -> BotIdentity:
        async with self._lifecycle_lock:
            if self._running:
                assert self._application is not None
                return self._identity(await self._application.bot.get_me())

            self._handler = handler
            app = Application.builder().token(self._token).build()
            self._application = app
            app.add_handler(CallbackQueryHandler(self._receive))
            app.add_handler(CommandHandler("start", self._receive))
            app.add_handler(MessageHandler(filters.ALL, self._receive))
            app.add_error_handler(self._ptb_error)

            try:
                await app.initialize()
                identity = self._identity(await app.bot.get_me())
                await app.start()
                if app.updater is None:
                    raise RuntimeError("PTB Application has no Updater for long polling")
                await app.updater.start_polling(
                    allowed_updates=("message", "callback_query"),
                    drop_pending_updates=self._drop_pending_updates,
                )
            except Exception:
                await self._cleanup_failed_start(app)
                self._application = None
                self._handler = None
                raise

            self._running = True
            return identity

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            app = self._application
            self._running = False
            self._handler = None
            if app is None:
                return
            errors: list[Exception] = []
            if app.updater is not None and app.updater.running:
                try:
                    await app.updater.stop()
                except Exception as exc:
                    errors.append(exc)
            if app.running:
                try:
                    await app.stop()
                except Exception as exc:
                    errors.append(exc)
            try:
                await app.shutdown()
            except Exception as exc:
                errors.append(exc)
            self._application = None
            if errors:
                raise RuntimeError(
                    "Telegram adapter shutdown failed: "
                    + "; ".join(str(error) for error in errors)
                ) from errors[0]

    async def send(self, message: OutboundMessage) -> Any:
        app = self._application
        if not self._running or app is None:
            raise RuntimeError("Telegram adapter is not running")
        markup = self._keyboard(message.keyboard)
        media = self._media_value(message.media)

        if message.media_kind is MediaKind.PHOTO:
            if media is None:
                raise ValueError("Photo message requires media")
            return await app.bot.send_photo(
                chat_id=message.chat_id,
                photo=media,
                caption=message.caption,
                parse_mode=message.parse_mode,
                reply_markup=markup,
                **dict(message.metadata),
            )
        if message.media_kind is MediaKind.DOCUMENT:
            if media is None:
                raise ValueError("Document message requires media")
            return await app.bot.send_document(
                chat_id=message.chat_id,
                document=media,
                caption=message.caption,
                parse_mode=message.parse_mode,
                reply_markup=markup,
                **dict(message.metadata),
            )
        if message.text is None:
            raise ValueError("Text message requires text")
        return await app.bot.send_message(
            chat_id=message.chat_id,
            text=message.text,
            parse_mode=message.parse_mode,
            reply_markup=markup,
            **dict(message.metadata),
        )

    async def _receive(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        del context
        if update.callback_query is not None:
            try:
                await update.callback_query.answer()
            except TelegramError:
                log.debug("Callback acknowledgement failed", exc_info=True)

        chat = update.effective_chat
        if chat is None:
            return
        if self._private_chats_only and chat.type != ChatType.PRIVATE:
            return
        converted = self._convert(update)
        if converted is None or self._handler is None:
            return
        try:
            await self._handler(converted)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("Runtime update handler failed")
            if self._error_handler is not None:
                try:
                    await self._error_handler(exc, converted)
                except Exception:
                    log.exception("Telegram adapter error callback failed")

    async def _ptb_error(
        self,
        update: object,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        error = context.error
        log.error("Unhandled PTB error", exc_info=error)
        if self._error_handler is not None and isinstance(error, Exception):
            try:
                await self._error_handler(
                    error,
                    self._convert(update) if isinstance(update, Update) else None,
                )
            except Exception:
                log.exception("Telegram adapter error callback failed")

    @staticmethod
    def _convert(update: Update) -> IncomingUpdate | None:
        user = update.effective_user
        chat = update.effective_chat
        message = update.effective_message
        if user is None or chat is None:
            return None

        if update.callback_query is not None:
            kind = UpdateKind.CALLBACK
            callback_data = update.callback_query.data or ""
            text = None
            command = None
        else:
            raw_text = message.text if message is not None else None
            callback_data = None
            if raw_text and raw_text.startswith("/"):
                kind = UpdateKind.COMMAND
                command_token = raw_text.split(maxsplit=1)[0][1:]
                command = command_token.split("@", maxsplit=1)[0].casefold()
                text = raw_text
            else:
                kind = UpdateKind.MESSAGE
                command = None
                text = raw_text or (message.caption if message is not None else None)

        return IncomingUpdate(
            update_id=update.update_id,
            telegram_user_id=user.id,
            telegram_chat_id=chat.id,
            kind=kind,
            text=text,
            callback_data=callback_data,
            command=command,
            message_id=message.message_id if message is not None else None,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            metadata={"chat_type": chat.type},
        )

    @staticmethod
    def _keyboard(keyboard: Keyboard | None) -> Any:
        if keyboard is None:
            return None
        if keyboard.kind is KeyboardKind.INLINE:
            rows = []
            for row in keyboard.rows:
                built = []
                for button in row:
                    if button.url:
                        built.append(InlineKeyboardButton(text=button.text, url=button.url))
                    elif button.value is not None:
                        built.append(
                            InlineKeyboardButton(
                                text=button.text,
                                callback_data=button.value,
                            )
                        )
                    else:
                        raise ValueError("Inline button requires value or url")
                rows.append(built)
            return InlineKeyboardMarkup(rows)
        return ReplyKeyboardMarkup(
            [
                [PtbKeyboardButton(text=button.text) for button in row]
                for row in keyboard.rows
            ],
            resize_keyboard=keyboard.resize,
            one_time_keyboard=keyboard.one_time,
        )

    @staticmethod
    def _media_value(value: str | bytes | None) -> Any:
        if isinstance(value, str):
            path = Path(value)
            if path.is_file():
                return path
        return value

    @staticmethod
    def _identity(user: Any) -> BotIdentity:
        display_name = " ".join(
            part for part in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if part
        ).strip()
        return BotIdentity(
            bot_id=int(user.id),
            username=str(user.username or ""),
            display_name=display_name or str(user.username or user.id),
        )

    @staticmethod
    async def _cleanup_failed_start(app: Application) -> None:
        try:
            if app.updater is not None and app.updater.running:
                await app.updater.stop()
        except Exception:
            pass
        try:
            if app.running:
                await app.stop()
        except Exception:
            pass
        try:
            await app.shutdown()
        except Exception:
            pass


PtbTelegramAdapter = PtbLongPollingAdapter

