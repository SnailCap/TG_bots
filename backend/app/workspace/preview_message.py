from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol, cast

from tg_bot_core.content import (
    CompiledTelegramMessage,
    ContentDiagnostic,
    TelegramMessageEntity,
)

from .repository import WorkspaceError


log = logging.getLogger(__name__)


class TelegramPreviewBotLike(Protocol):
    async def send_message(self, **kwargs: Any) -> object: ...


PreviewBotFactory = Callable[
    [str], TelegramPreviewBotLike | Awaitable[TelegramPreviewBotLike]
]


class PreviewMessageRequestError(WorkspaceError):
    status_code = 422
    code = "invalid_preview_message_request"


class PreviewMessageCompileError(WorkspaceError):
    status_code = 422
    code = "content_compile_failed"

    def __init__(self, diagnostics: Sequence[ContentDiagnostic]) -> None:
        super().__init__("Content has blocking compiler errors; no message was sent.")
        self.diagnostics = tuple(diagnostics)


class PreviewMessageConfigurationError(WorkspaceError):
    status_code = 409
    code = "telegram_bot_token_missing"


class PreviewMessageDeliveryError(WorkspaceError):
    status_code = 502
    code = "telegram_preview_send_failed"

    def __init__(self, sent_count: int, total_count: int) -> None:
        super().__init__(
            "Telegram could not deliver the preview message. "
            f"Sent {sent_count} of {total_count} chunks."
        )
        self.sent_count = sent_count
        self.total_count = total_count


@dataclass(frozen=True, slots=True)
class PreviewMessageSendResult:
    sent_count: int
    total_count: int
    message_ids: tuple[int | None, ...]
    warnings: tuple[ContentDiagnostic, ...] = ()

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "sent": True,
            "sentCount": self.sent_count,
            "totalCount": self.total_count,
            "messageIds": list(self.message_ids),
            "warnings": [diagnostic_to_api_dict(item) for item in self.warnings],
        }


def diagnostic_to_api_dict(diagnostic: ContentDiagnostic) -> dict[str, Any]:
    return {
        "severity": diagnostic.severity,
        "code": diagnostic.code,
        "message": diagnostic.message,
        **({"path": diagnostic.path} if diagnostic.path is not None else {}),
    }


def normalize_preview_chat_id(chat_id: int | str) -> int | str:
    if isinstance(chat_id, bool) or not isinstance(chat_id, (int, str)):
        raise PreviewMessageRequestError(
            "chatId must be an integer or non-empty string."
        )
    if isinstance(chat_id, int):
        return chat_id
    normalized = chat_id.strip()
    if not normalized or len(normalized) > 128 or any(
        character in normalized for character in ("\r", "\n", "\0")
    ):
        raise PreviewMessageRequestError(
            "chatId must be an integer or non-empty string of at most 128 characters."
        )
    return normalized


class PreviewMessageSender:
    """Explicitly send already-compiled Telegram chunks for Studio preview."""

    def __init__(self, *, bot_factory: PreviewBotFactory | None = None) -> None:
        self._bot_factory = bot_factory or _default_bot_factory

    async def send(
        self,
        messages: Sequence[CompiledTelegramMessage],
        *,
        chat_id: int | str,
        bot_token: str,
        warnings: Sequence[ContentDiagnostic] = (),
    ) -> PreviewMessageSendResult:
        destination = normalize_preview_chat_id(chat_id)
        token = bot_token.strip()
        if not token:
            raise PreviewMessageConfigurationError(
                "Configure BOT_TOKEN in this project's settings before sending a preview."
            )

        total_count = len(messages)
        message_ids: list[int | None] = []
        sent_count = 0
        try:
            async with self._client_scope(token) as bot:
                for message in messages:
                    response = await bot.send_message(
                        chat_id=destination,
                        text=message.text,
                        entities=[
                            self._message_entity(entity)
                            for entity in message.entities
                        ]
                        or None,
                        disable_notification=True,
                    )
                    message_id = getattr(response, "message_id", None)
                    message_ids.append(
                        message_id
                        if isinstance(message_id, int)
                        and not isinstance(message_id, bool)
                        else None
                    )
                    sent_count += 1
        except PreviewMessageRequestError:
            raise
        except Exception as error:
            # Telegram/http exceptions may include the bot token in their message
            # or request URL. Neither logs nor the API error derive text from them.
            del error
            log.warning(
                "Could not send Telegram preview message (%d of %d chunks sent).",
                sent_count,
                total_count,
            )
            raise PreviewMessageDeliveryError(sent_count, total_count) from None

        return PreviewMessageSendResult(
            sent_count=sent_count,
            total_count=total_count,
            message_ids=tuple(message_ids),
            warnings=tuple(warnings),
        )

    @staticmethod
    def _message_entity(entity: TelegramMessageEntity):
        from telegram import MessageEntity

        return MessageEntity(
            type=entity.type,
            offset=entity.offset,
            length=entity.length,
            url=entity.url,
            language=entity.language,
            custom_emoji_id=entity.custom_emoji_id,
        )

    @asynccontextmanager
    async def _client_scope(
        self, token: str
    ) -> AsyncIterator[TelegramPreviewBotLike]:
        created = self._bot_factory(token)
        bot = await created if inspect.isawaitable(created) else created
        try:
            initializer = getattr(bot, "initialize", None)
            if callable(initializer):
                initialized = initializer()
                if inspect.isawaitable(initialized):
                    await initialized
            yield bot
        finally:
            shutdown = getattr(bot, "shutdown", None)
            if callable(shutdown):
                try:
                    stopped = shutdown()
                    if inspect.isawaitable(stopped):
                        await stopped
                except Exception as error:
                    del error
                    log.warning("Could not close Telegram preview client.")


def _default_bot_factory(token: str) -> TelegramPreviewBotLike:
    from telegram import Bot

    return cast(TelegramPreviewBotLike, Bot(token=token))
