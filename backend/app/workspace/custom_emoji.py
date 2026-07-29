from __future__ import annotations

import inspect
import json
import logging
import os
import re
import tempfile
import threading
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol, cast

from .repository import WorkspaceRepository


log = logging.getLogger(__name__)

MAX_CUSTOM_EMOJI_IDS = 200
MAX_PREVIEW_BYTES = 5 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024
DEFAULT_FALLBACK_EMOJI = "🙂"

_ID_PATTERN = re.compile(r"^[0-9]{1,32}$", re.ASCII)
_PREVIEW_TYPES: dict[str, tuple[str, str]] = {
    ".webp": ("webp", "image/webp"),
    ".tgs": ("tgs", "application/x-tgsticker"),
    ".webm": ("webm", "video/webm"),
}
_PREVIEW_EXTENSIONS = {format_name: suffix for suffix, (format_name, _) in _PREVIEW_TYPES.items()}
_PREVIEW_MIME_TYPES = {format_name: mime_type for _, (format_name, mime_type) in _PREVIEW_TYPES.items()}
_SOURCES = {"telegram-message", "sticker-set", "manual-id", "recent", "favorite"}
_RESOLVE_STATUSES = {"resolved", "fallback-only", "unavailable"}
_REASONS = {
    "missing-token",
    "network-error",
    "capability-unavailable",
    "not-found",
    "unavailable-preview",
    "unsupported-preview",
    "invalid-preview",
    "preview-too-large",
    "cache-error",
}

CustomEmojiSource = Literal[
    "telegram-message", "sticker-set", "manual-id", "recent", "favorite"
]
CustomEmojiResolveStatus = Literal["resolved", "fallback-only", "unavailable"]
CustomEmojiFailureReason = Literal[
    "missing-token",
    "network-error",
    "capability-unavailable",
    "not-found",
    "unavailable-preview",
    "unsupported-preview",
    "invalid-preview",
    "preview-too-large",
    "cache-error",
]
CustomEmojiCapability = Literal["unknown", "available", "unavailable", "test-required"]
PreviewFormat = Literal["webp", "tgs", "webm"]


class CustomEmojiRequestError(ValueError):
    """The caller supplied an invalid custom-emoji request."""

    code = "invalid_custom_emoji_request"


class TelegramFileLike(Protocol):
    file_path: str | None
    file_size: int | None

    async def download_to_memory(self, *, out: BytesIO) -> object: ...


class TelegramStickerLike(Protocol):
    custom_emoji_id: str | None
    file_id: str
    file_unique_id: str
    width: int
    height: int
    is_animated: bool
    is_video: bool
    needs_repainting: bool | None
    emoji: str | None


class TelegramBotLike(Protocol):
    async def get_custom_emoji_stickers(
        self, custom_emoji_ids: Sequence[str]
    ) -> Sequence[TelegramStickerLike]: ...

    async def get_file(self, file_id: str) -> TelegramFileLike: ...

    async def send_message(self, **kwargs: Any) -> object: ...


BotFactory = Callable[
    [str], TelegramBotLike | Awaitable[TelegramBotLike]
]


@dataclass(frozen=True, slots=True)
class CustomEmojiStickerMetadata:
    file_id: str | None = None
    file_unique_id: str | None = None
    width: int | None = None
    height: int | None = None
    is_animated: bool = False
    is_video: bool = False
    needs_repainting: bool | None = None

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "fileId": self.file_id,
            "fileUniqueId": self.file_unique_id,
            "width": self.width,
            "height": self.height,
            "isAnimated": self.is_animated,
            "isVideo": self.is_video,
            "needsRepainting": self.needs_repainting,
        }


@dataclass(frozen=True, slots=True)
class CustomEmojiItem:
    id: str
    fallback_emoji: str
    status: CustomEmojiResolveStatus
    source: CustomEmojiSource
    last_used_at: str
    last_checked_at: str
    reason: CustomEmojiFailureReason | None = None
    sticker: CustomEmojiStickerMetadata | None = None
    preview_format: PreviewFormat | None = None
    loaded_at: str | None = None
    cached: bool = False

    @property
    def preview_key(self) -> str | None:
        # This is deliberately opaque to the renderer. It is not a filesystem path.
        return self.id if self.preview_format is not None else None

    def to_api_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "fallbackEmoji": self.fallback_emoji,
            "status": self.status,
            "source": self.source,
            "lastUsedAt": self.last_used_at,
            "lastCheckedAt": self.last_checked_at,
            "cached": self.cached,
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.sticker is not None:
            payload["sticker"] = self.sticker.to_api_dict()
        if self.preview_format is not None and self.loaded_at is not None:
            payload["previewKey"] = self.id
            payload["preview"] = {
                "key": self.id,
                "format": self.preview_format,
                "mimeType": _PREVIEW_MIME_TYPES[self.preview_format],
                "loadedAt": self.loaded_at,
            }
        return payload


@dataclass(frozen=True, slots=True)
class CustomEmojiResolveResult:
    items: tuple[CustomEmojiItem, ...]

    def to_api_dict(self) -> dict[str, Any]:
        return {"items": [item.to_api_dict() for item in self.items]}


@dataclass(frozen=True, slots=True)
class CachedCustomEmojiPreview:
    """Backend-only cache handle. Never serialize this object to the renderer."""

    path: Path
    mime_type: str


@dataclass(frozen=True, slots=True)
class CustomEmojiCapabilityResult:
    capability: CustomEmojiCapability
    reason: CustomEmojiFailureReason | None = None

    def to_api_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"capability": self.capability}
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


def validate_custom_emoji_ids(custom_emoji_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(custom_emoji_ids, (str, bytes)) or not isinstance(
        custom_emoji_ids, Sequence
    ):
        raise CustomEmojiRequestError("customEmojiIds must be an array of decimal strings.")
    if len(custom_emoji_ids) > MAX_CUSTOM_EMOJI_IDS:
        raise CustomEmojiRequestError(
            f"customEmojiIds may contain at most {MAX_CUSTOM_EMOJI_IDS} items."
        )

    unique: list[str] = []
    seen: set[str] = set()
    for custom_emoji_id in custom_emoji_ids:
        if not isinstance(custom_emoji_id, str) or not _ID_PATTERN.fullmatch(
            custom_emoji_id
        ):
            raise CustomEmojiRequestError(
                "Every custom emoji ID must be an ASCII decimal string."
            )
        if custom_emoji_id not in seen:
            seen.add(custom_emoji_id)
            unique.append(custom_emoji_id)
    return tuple(unique)


def default_custom_emoji_cache_root(
    env: Mapping[str, str] | None = None, *, temp_root: Path | None = None
) -> Path:
    values = os.environ if env is None else env
    for variable in ("APPDATA", "LOCALAPPDATA"):
        raw = values.get(variable)
        if raw:
            candidate = Path(raw).expanduser()
            if candidate.is_absolute():
                return candidate / "BotStudio" / "cache" / "custom-emoji"
    fallback = temp_root or Path(tempfile.gettempdir())
    return fallback.expanduser().resolve(strict=False) / "BotStudio" / "cache" / "custom-emoji"


class CustomEmojiService:
    """Resolve Telegram custom emoji and maintain Studio's untrusted preview cache."""

    def __init__(
        self,
        cache_root: str | Path | None = None,
        *,
        bot_factory: BotFactory | None = None,
        clock: Callable[[], datetime] | None = None,
        max_preview_bytes: int = MAX_PREVIEW_BYTES,
    ) -> None:
        if max_preview_bytes <= 0:
            raise ValueError("max_preview_bytes must be positive.")
        root = Path(cache_root) if cache_root is not None else default_custom_emoji_cache_root()
        self._cache_root = root.expanduser().resolve(strict=False)
        self._bot_factory = bot_factory or _default_bot_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._max_preview_bytes = max_preview_bytes
        self._cache_lock = threading.RLock()

    async def resolve(
        self,
        custom_emoji_ids: Sequence[str],
        *,
        bot_token: str | None = None,
        client: TelegramBotLike | None = None,
        fallback_by_id: Mapping[str, str] | None = None,
        source: CustomEmojiSource = "manual-id",
    ) -> CustomEmojiResolveResult:
        ids = validate_custom_emoji_ids(custom_emoji_ids)
        if source not in _SOURCES:
            raise CustomEmojiRequestError("Unsupported custom emoji source.")
        if not ids:
            return CustomEmojiResolveResult(())

        now = self._timestamp()
        cached = {custom_emoji_id: self._load_record(custom_emoji_id) for custom_emoji_id in ids}
        fallbacks = {
            custom_emoji_id: self._fallback_for(
                custom_emoji_id, fallback_by_id, cached[custom_emoji_id], None
            )
            for custom_emoji_id in ids
        }

        normalized_token = bot_token.strip() if isinstance(bot_token, str) else ""
        if client is None and not normalized_token:
            return self._failure_result(
                ids,
                cached,
                fallbacks,
                source,
                now,
                reason="missing-token",
            )

        try:
            async with self._client_scope(normalized_token, client) as bot:
                stickers = await bot.get_custom_emoji_stickers(
                    custom_emoji_ids=list(ids)
                )
                stickers_by_id = self._index_stickers(stickers, ids)
                items: list[CustomEmojiItem] = []
                for custom_emoji_id in ids:
                    sticker = stickers_by_id.get(custom_emoji_id)
                    if sticker is None:
                        record = self._failure_record(
                            custom_emoji_id,
                            cached[custom_emoji_id],
                            fallbacks[custom_emoji_id],
                            source,
                            now,
                            reason="not-found",
                        )
                    else:
                        fallback = self._fallback_for(
                            custom_emoji_id,
                            fallback_by_id,
                            cached[custom_emoji_id],
                            sticker,
                        )
                        record = await self._resolve_sticker(
                            bot,
                            custom_emoji_id,
                            sticker,
                            cached[custom_emoji_id],
                            fallback,
                            source,
                            now,
                        )
                    items.append(self._persist_for_response(record))
                return CustomEmojiResolveResult(tuple(items))
        except Exception as error:
            reason = _classify_remote_error(error)
            _log_safe_remote_error("resolve custom emoji", error)
            return self._failure_result(
                ids, cached, fallbacks, source, now, reason=reason
            )

    def resolve_cached_preview(
        self, custom_emoji_id: str
    ) -> CachedCustomEmojiPreview | None:
        identifier = _validate_one_id(custom_emoji_id)
        record = self._load_record(identifier)
        if record is None or record.preview_format is None:
            return None
        path = self._preview_path(identifier, record.preview_format)
        if path.is_symlink() or not path.is_file():
            return None
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(self._cache_root):
                return None
            size = resolved.stat().st_size
            if size <= 0 or size > self._max_preview_bytes:
                return None
            with resolved.open("rb") as stream:
                header = stream.read(12)
        except OSError:
            return None
        suffix = _PREVIEW_EXTENSIONS[record.preview_format]
        if not _valid_preview_signature(suffix, header):
            return None
        return CachedCustomEmojiPreview(
            path=resolved,
            mime_type=_PREVIEW_MIME_TYPES[record.preview_format],
        )

    async def test_capability(
        self,
        custom_emoji_id: str,
        *,
        chat_id: int | str | None,
        bot_token: str | None = None,
        client: TelegramBotLike | None = None,
        fallback_emoji: str = DEFAULT_FALLBACK_EMOJI,
    ) -> CustomEmojiCapabilityResult:
        identifier = _validate_one_id(custom_emoji_id)
        if chat_id is None:
            return CustomEmojiCapabilityResult("test-required")
        if isinstance(chat_id, bool) or not isinstance(chat_id, (int, str)):
            raise CustomEmojiRequestError("chatId must be an integer or non-empty string.")
        if isinstance(chat_id, str) and not chat_id.strip():
            raise CustomEmojiRequestError("chatId must be an integer or non-empty string.")

        normalized_token = bot_token.strip() if isinstance(bot_token, str) else ""
        if client is None and not normalized_token:
            return CustomEmojiCapabilityResult("unknown", "missing-token")

        fallback = _normalize_fallback(fallback_emoji)
        try:
            from telegram import MessageEntity

            entity = MessageEntity(
                type=MessageEntity.CUSTOM_EMOJI,
                offset=0,
                length=_utf16_length(fallback),
                custom_emoji_id=identifier,
            )
            async with self._client_scope(normalized_token, client) as bot:
                # Sending is intentionally isolated to this explicitly invoked method.
                # It is never called as part of resolve() or cache reads.
                await bot.send_message(
                    chat_id=chat_id,
                    text=fallback,
                    entities=[entity],
                    disable_notification=True,
                )
            return CustomEmojiCapabilityResult("available")
        except Exception as error:
            reason = _classify_remote_error(error)
            _log_safe_remote_error("test custom emoji capability", error)
            capability: CustomEmojiCapability = (
                "unavailable" if reason == "capability-unavailable" else "unknown"
            )
            return CustomEmojiCapabilityResult(capability, reason)

    async def _resolve_sticker(
        self,
        bot: TelegramBotLike,
        custom_emoji_id: str,
        sticker: TelegramStickerLike,
        cached: CustomEmojiItem | None,
        fallback: str,
        source: CustomEmojiSource,
        now: str,
    ) -> CustomEmojiItem:
        metadata = _sticker_metadata(sticker)
        file_id = metadata.file_id
        if not file_id:
            return self._failure_record(
                custom_emoji_id,
                cached,
                fallback,
                source,
                now,
                reason="unavailable-preview",
                sticker=metadata,
            )

        try:
            telegram_file = await bot.get_file(file_id=file_id)
            file_size = getattr(telegram_file, "file_size", None)
            if isinstance(file_size, int) and file_size > self._max_preview_bytes:
                return self._failure_record(
                    custom_emoji_id,
                    cached,
                    fallback,
                    source,
                    now,
                    reason="preview-too-large",
                    sticker=metadata,
                )

            file_path = getattr(telegram_file, "file_path", None)
            suffix = (
                PurePosixPath(file_path).suffix.lower()
                if isinstance(file_path, str)
                else ""
            )
            preview_type = _PREVIEW_TYPES.get(suffix)
            if preview_type is None:
                return self._failure_record(
                    custom_emoji_id,
                    cached,
                    fallback,
                    source,
                    now,
                    reason="unsupported-preview",
                    sticker=metadata,
                )

            output = BytesIO()
            await telegram_file.download_to_memory(out=output)
            content = output.getvalue()
            if len(content) > self._max_preview_bytes:
                reason: CustomEmojiFailureReason = "preview-too-large"
            elif not _valid_preview_signature(suffix, content):
                reason = "invalid-preview"
            else:
                preview_format = cast(PreviewFormat, preview_type[0])
                try:
                    WorkspaceRepository.atomic_write(
                        self._preview_path(custom_emoji_id, preview_format), content
                    )
                except OSError as error:
                    _log_safe_remote_error("write custom emoji preview cache", error)
                    reason = "cache-error"
                else:
                    return CustomEmojiItem(
                        id=custom_emoji_id,
                        fallback_emoji=fallback,
                        status="resolved",
                        source=source,
                        last_used_at=now,
                        last_checked_at=now,
                        sticker=metadata,
                        preview_format=preview_format,
                        loaded_at=now,
                    )
            return self._failure_record(
                custom_emoji_id,
                cached,
                fallback,
                source,
                now,
                reason=reason,
                sticker=metadata,
            )
        except Exception as error:
            _log_safe_remote_error("download custom emoji preview", error)
            return self._failure_record(
                custom_emoji_id,
                cached,
                fallback,
                source,
                now,
                reason=_classify_preview_error(error),
                sticker=metadata,
            )

    def _failure_result(
        self,
        ids: Sequence[str],
        cached: Mapping[str, CustomEmojiItem | None],
        fallbacks: Mapping[str, str],
        source: CustomEmojiSource,
        now: str,
        *,
        reason: CustomEmojiFailureReason,
    ) -> CustomEmojiResolveResult:
        items = tuple(
            self._persist_for_response(
                self._failure_record(
                    custom_emoji_id,
                    cached[custom_emoji_id],
                    fallbacks[custom_emoji_id],
                    source,
                    now,
                    reason=reason,
                )
            )
            for custom_emoji_id in ids
        )
        return CustomEmojiResolveResult(items)

    def _failure_record(
        self,
        custom_emoji_id: str,
        cached: CustomEmojiItem | None,
        fallback: str,
        source: CustomEmojiSource,
        now: str,
        *,
        reason: CustomEmojiFailureReason,
        sticker: CustomEmojiStickerMetadata | None = None,
    ) -> CustomEmojiItem:
        preview_format: PreviewFormat | None = None
        loaded_at: str | None = None
        if cached is not None and cached.preview_format is not None:
            preview = self.resolve_cached_preview(custom_emoji_id)
            if preview is not None:
                preview_format = cached.preview_format
                loaded_at = cached.loaded_at

        status: CustomEmojiResolveStatus
        if preview_format is not None:
            status = "resolved"
        elif reason == "not-found":
            status = "unavailable"
        else:
            status = "fallback-only"
        return CustomEmojiItem(
            id=custom_emoji_id,
            fallback_emoji=fallback,
            status=status,
            source=source,
            last_used_at=now,
            last_checked_at=now,
            reason=reason,
            sticker=sticker or (cached.sticker if cached else None),
            preview_format=preview_format,
            loaded_at=loaded_at,
            cached=preview_format is not None,
        )

    def _persist_for_response(self, record: CustomEmojiItem) -> CustomEmojiItem:
        if self._store_record(record):
            return record
        if record.preview_format is None:
            return replace(record, reason="cache-error")
        return replace(
            record,
            status="fallback-only",
            reason="cache-error",
            preview_format=None,
            loaded_at=None,
        )

    def _load_record(self, custom_emoji_id: str) -> CustomEmojiItem | None:
        path = self._metadata_path(custom_emoji_id)
        if path.is_symlink() or not path.is_file():
            return None
        try:
            if path.stat().st_size > MAX_METADATA_BYTES:
                raise ValueError("Custom emoji cache metadata is too large.")
            raw = json.loads(path.read_text(encoding="utf-8"))
            return _record_from_cache(raw, custom_emoji_id)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            _log_safe_remote_error("read custom emoji metadata cache", error)
            return None

    def _store_record(self, record: CustomEmojiItem) -> bool:
        payload: dict[str, Any] = {
            "schemaVersion": 1,
            **record.to_api_dict(),
            "loadedAt": record.loaded_at,
            "previewFormat": record.preview_format,
        }
        try:
            with self._cache_lock:
                WorkspaceRepository.atomic_write_json(
                    self._metadata_path(record.id), payload
                )
            return True
        except OSError as error:
            _log_safe_remote_error("write custom emoji metadata cache", error)
            return False

    def _metadata_path(self, custom_emoji_id: str) -> Path:
        return self._cache_path(custom_emoji_id, ".json")

    def _preview_path(
        self, custom_emoji_id: str, preview_format: PreviewFormat
    ) -> Path:
        return self._cache_path(
            custom_emoji_id, _PREVIEW_EXTENSIONS[preview_format]
        )

    def _cache_path(self, custom_emoji_id: str, suffix: str) -> Path:
        identifier = _validate_one_id(custom_emoji_id)
        if suffix not in {*_PREVIEW_TYPES, ".json"}:
            raise ValueError("Unsupported custom emoji cache suffix.")
        candidate = self._cache_root / f"{identifier}{suffix}"
        if candidate.parent != self._cache_root:
            raise CustomEmojiRequestError("Invalid custom emoji cache key.")
        return candidate

    def _timestamp(self) -> str:
        value = self._clock()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )

    @staticmethod
    def _fallback_for(
        custom_emoji_id: str,
        fallbacks: Mapping[str, str] | None,
        cached: CustomEmojiItem | None,
        sticker: TelegramStickerLike | None,
    ) -> str:
        requested = fallbacks.get(custom_emoji_id) if fallbacks else None
        if isinstance(requested, str) and requested.strip():
            return _normalize_fallback(requested)
        sticker_emoji = getattr(sticker, "emoji", None)
        if isinstance(sticker_emoji, str) and sticker_emoji.strip():
            return _normalize_fallback(sticker_emoji)
        if cached is not None and cached.fallback_emoji:
            return cached.fallback_emoji
        return DEFAULT_FALLBACK_EMOJI

    @staticmethod
    def _index_stickers(
        stickers: Sequence[TelegramStickerLike], ids: Sequence[str]
    ) -> dict[str, TelegramStickerLike]:
        requested = set(ids)
        indexed: dict[str, TelegramStickerLike] = {}
        for sticker in stickers:
            identifier = getattr(sticker, "custom_emoji_id", None)
            if (
                isinstance(identifier, str)
                and identifier in requested
                and identifier not in indexed
            ):
                indexed[identifier] = sticker
        return indexed

    @asynccontextmanager
    async def _client_scope(
        self, token: str, provided: TelegramBotLike | None
    ) -> AsyncIterator[TelegramBotLike]:
        if provided is not None:
            yield provided
            return

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
                    _log_safe_remote_error("close Telegram custom emoji client", error)


def _validate_one_id(custom_emoji_id: str) -> str:
    ids = validate_custom_emoji_ids([custom_emoji_id])
    return ids[0]


def _default_bot_factory(token: str) -> TelegramBotLike:
    from telegram import Bot

    return cast(TelegramBotLike, Bot(token=token))


def _normalize_fallback(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        return DEFAULT_FALLBACK_EMOJI
    normalized = value.strip()
    return normalized if len(normalized) <= 32 else DEFAULT_FALLBACK_EMOJI


def _sticker_metadata(sticker: TelegramStickerLike) -> CustomEmojiStickerMetadata:
    return CustomEmojiStickerMetadata(
        file_id=_optional_nonempty_string(getattr(sticker, "file_id", None)),
        file_unique_id=_optional_nonempty_string(
            getattr(sticker, "file_unique_id", None)
        ),
        width=_optional_positive_int(getattr(sticker, "width", None)),
        height=_optional_positive_int(getattr(sticker, "height", None)),
        is_animated=bool(getattr(sticker, "is_animated", False)),
        is_video=bool(getattr(sticker, "is_video", False)),
        needs_repainting=_optional_bool(
            getattr(sticker, "needs_repainting", None)
        ),
    )


def _record_from_cache(raw: object, custom_emoji_id: str) -> CustomEmojiItem:
    if (
        not isinstance(raw, dict)
        or type(raw.get("schemaVersion")) is not int
        or raw.get("schemaVersion") != 1
    ):
        raise ValueError("Unsupported custom emoji cache metadata.")
    if raw.get("id") != custom_emoji_id:
        raise ValueError("Custom emoji cache ID mismatch.")
    status = raw.get("status")
    source = raw.get("source")
    reason = raw.get("reason")
    if status not in _RESOLVE_STATUSES or source not in _SOURCES:
        raise ValueError("Invalid custom emoji cache metadata.")
    if reason is not None and reason not in _REASONS:
        raise ValueError("Invalid custom emoji cache reason.")
    fallback = _normalize_fallback(raw.get("fallbackEmoji"))
    last_used_at = _required_string(raw.get("lastUsedAt"))
    last_checked_at = _required_string(raw.get("lastCheckedAt"))
    loaded_at = _optional_nonempty_string(raw.get("loadedAt"))
    preview_format_raw = raw.get("previewFormat")
    preview_format: PreviewFormat | None = None
    if preview_format_raw is not None:
        if preview_format_raw not in _PREVIEW_EXTENSIONS:
            raise ValueError("Invalid custom emoji preview format.")
        preview_format = cast(PreviewFormat, preview_format_raw)

    sticker_raw = raw.get("sticker")
    sticker: CustomEmojiStickerMetadata | None = None
    if isinstance(sticker_raw, dict):
        sticker = CustomEmojiStickerMetadata(
            file_id=_optional_nonempty_string(sticker_raw.get("fileId")),
            file_unique_id=_optional_nonempty_string(
                sticker_raw.get("fileUniqueId")
            ),
            width=_optional_positive_int(sticker_raw.get("width")),
            height=_optional_positive_int(sticker_raw.get("height")),
            is_animated=sticker_raw.get("isAnimated") is True,
            is_video=sticker_raw.get("isVideo") is True,
            needs_repainting=_optional_bool(sticker_raw.get("needsRepainting")),
        )
    return CustomEmojiItem(
        id=custom_emoji_id,
        fallback_emoji=fallback,
        status=cast(CustomEmojiResolveStatus, status),
        source=cast(CustomEmojiSource, source),
        last_used_at=last_used_at,
        last_checked_at=last_checked_at,
        reason=cast(CustomEmojiFailureReason | None, reason),
        sticker=sticker,
        preview_format=preview_format,
        loaded_at=loaded_at,
        cached=True,
    )


def _valid_preview_signature(suffix: str, content: bytes) -> bool:
    if suffix == ".webp":
        return (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )
    if suffix == ".tgs":
        return content.startswith(b"\x1f\x8b")
    if suffix == ".webm":
        return content.startswith(b"\x1aE\xdf\xa3")
    return False


def _classify_remote_error(error: Exception) -> CustomEmojiFailureReason:
    name = type(error).__name__.lower()
    if any(
        marker in name
        for marker in ("invalidtoken", "unauthorized", "forbidden", "badrequest")
    ):
        return "capability-unavailable"
    return "network-error"


def _classify_preview_error(error: Exception) -> CustomEmojiFailureReason:
    return (
        "unavailable-preview"
        if _classify_remote_error(error) == "capability-unavailable"
        else "network-error"
    )


def _log_safe_remote_error(operation: str, error: Exception) -> None:
    # Telegram InvalidToken and HTTP errors can contain the token in their message/URL.
    # Do not derive any log field from the exception: injected clients and HTTP
    # libraries may include the bot token even in unusual exception metadata.
    del error
    log.warning("Could not %s.", operation)


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _required_string(value: object) -> str:
    normalized = _optional_nonempty_string(value)
    if normalized is None:
        raise ValueError("Expected a non-empty string.")
    return normalized


def _optional_nonempty_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


__all__ = [
    "CachedCustomEmojiPreview",
    "CustomEmojiCapabilityResult",
    "CustomEmojiItem",
    "CustomEmojiRequestError",
    "CustomEmojiResolveResult",
    "CustomEmojiService",
    "CustomEmojiStickerMetadata",
    "default_custom_emoji_cache_root",
    "validate_custom_emoji_ids",
]
