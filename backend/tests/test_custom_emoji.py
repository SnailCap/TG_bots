from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from app.workspace.custom_emoji import (
    CustomEmojiRequestError,
    CustomEmojiService,
    default_custom_emoji_cache_root,
    validate_custom_emoji_ids,
)


FIXED_TIME = datetime(2026, 7, 29, 10, 30, tzinfo=timezone.utc)


@dataclass
class FakeSticker:
    custom_emoji_id: str
    file_id: str = "file-id"
    file_unique_id: str = "file-unique-id"
    width: int = 100
    height: int = 100
    is_animated: bool = False
    is_video: bool = False
    needs_repainting: bool | None = False
    emoji: str | None = "👍"


class FakeTelegramFile:
    def __init__(self, file_path: str, content: bytes, *, file_size: int | None = None) -> None:
        self.file_path = file_path
        self.file_size = len(content) if file_size is None else file_size
        self.content = content
        self.downloads = 0

    async def download_to_memory(self, *, out: BytesIO) -> None:
        self.downloads += 1
        out.write(self.content)


class FakeBot:
    def __init__(
        self,
        *,
        stickers: list[FakeSticker] | None = None,
        files: dict[str, FakeTelegramFile] | None = None,
        resolve_error: Exception | None = None,
        send_error: Exception | None = None,
    ) -> None:
        self.stickers = stickers or []
        self.files = files or {}
        self.resolve_error = resolve_error
        self.send_error = send_error
        self.custom_emoji_calls: list[tuple[str, ...]] = []
        self.file_calls: list[str] = []
        self.sent_messages: list[dict[str, Any]] = []
        self.initialized = 0
        self.shutdowns = 0

    async def initialize(self) -> None:
        self.initialized += 1

    async def shutdown(self) -> None:
        self.shutdowns += 1

    async def get_custom_emoji_stickers(
        self, custom_emoji_ids: list[str]
    ) -> list[FakeSticker]:
        self.custom_emoji_calls.append(tuple(custom_emoji_ids))
        if self.resolve_error is not None:
            raise self.resolve_error
        return self.stickers

    async def get_file(self, file_id: str) -> FakeTelegramFile:
        self.file_calls.append(file_id)
        return self.files[file_id]

    async def send_message(self, **kwargs: Any) -> object:
        self.sent_messages.append(kwargs)
        if self.send_error is not None:
            raise self.send_error
        return object()


def _service(cache_root: Path, **kwargs: Any) -> CustomEmojiService:
    return CustomEmojiService(
        cache_root,
        clock=lambda: FIXED_TIME,
        **kwargs,
    )


def test_validates_ascii_decimal_ids_deduplicates_and_caps_the_raw_batch() -> None:
    assert validate_custom_emoji_ids(["123", "123", "456"]) == ("123", "456")

    for invalid in ("../123", "123/456", "123.webp", "١٢٣", "", "1\\2"):
        with pytest.raises(CustomEmojiRequestError, match="ASCII decimal"):
            validate_custom_emoji_ids([invalid])

    with pytest.raises(CustomEmojiRequestError, match="at most 200"):
        validate_custom_emoji_ids(["1"] * 201)
    with pytest.raises(CustomEmojiRequestError, match="array"):
        validate_custom_emoji_ids("123")  # type: ignore[arg-type]


def test_default_cache_root_prefers_appdata_then_localappdata_then_temp(
    tmp_path: Path,
) -> None:
    appdata = tmp_path / "roaming"
    local = tmp_path / "local"
    assert default_custom_emoji_cache_root(
        {"APPDATA": str(appdata), "LOCALAPPDATA": str(local)}
    ) == appdata / "BotStudio" / "cache" / "custom-emoji"
    assert default_custom_emoji_cache_root(
        {"LOCALAPPDATA": str(local)}
    ) == local / "BotStudio" / "cache" / "custom-emoji"
    assert default_custom_emoji_cache_root({}, temp_root=tmp_path / "temp") == (
        tmp_path / "temp" / "BotStudio" / "cache" / "custom-emoji"
    )


@pytest.mark.asyncio
async def test_resolve_batches_deduplicated_ids_caches_atomically_and_returns_no_path(
    tmp_path: Path,
) -> None:
    webp = FakeTelegramFile(
        "stickers/custom.webp", b"RIFF\x04\x00\x00\x00WEBPpayload"
    )
    bot = FakeBot(
        stickers=[FakeSticker("111")],
        files={"file-id": webp},
    )
    factory_tokens: list[str] = []

    def factory(token: str) -> FakeBot:
        factory_tokens.append(token)
        return bot

    service = _service(tmp_path / "cache", bot_factory=factory)
    result = await service.resolve(
        ["111", "111", "222"], bot_token="123456:secret-token"
    )

    assert factory_tokens == ["123456:secret-token"]
    assert bot.initialized == 1
    assert bot.shutdowns == 1
    assert bot.custom_emoji_calls == [("111", "222")]
    assert bot.file_calls == ["file-id"]
    assert bot.sent_messages == []

    resolved, unavailable = result.items
    assert resolved.status == "resolved"
    assert resolved.fallback_emoji == "👍"
    assert resolved.preview_key == "111"
    assert resolved.loaded_at == "2026-07-29T10:30:00Z"
    assert resolved.last_used_at == "2026-07-29T10:30:00Z"
    assert resolved.last_checked_at == "2026-07-29T10:30:00Z"
    assert unavailable.status == "unavailable"
    assert unavailable.reason == "not-found"

    api_payload = result.to_api_dict()
    serialized = json.dumps(api_payload)
    assert api_payload["items"][0]["previewKey"] == "111"
    assert api_payload["items"][0]["preview"] == {
        "key": "111",
        "format": "webp",
        "mimeType": "image/webp",
        "loadedAt": "2026-07-29T10:30:00Z",
    }
    assert str(tmp_path) not in serialized
    assert "secret-token" not in serialized

    preview = service.resolve_cached_preview("111")
    assert preview is not None
    assert preview.mime_type == "image/webp"
    assert preview.path.name == "111.webp"
    assert preview.path.read_bytes() == webp.content

    metadata = json.loads((tmp_path / "cache" / "111.json").read_text("utf-8"))
    assert metadata["id"] == "111"
    assert metadata["loadedAt"] == "2026-07-29T10:30:00Z"
    assert metadata["lastUsedAt"] == "2026-07-29T10:30:00Z"
    assert metadata["lastCheckedAt"] == "2026-07-29T10:30:00Z"
    assert not list((tmp_path / "cache").glob("*.tmp"))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("suffix", "content", "expected_format", "expected_mime"),
    [
        (".webp", b"RIFF\x04\x00\x00\x00WEBPdata", "webp", "image/webp"),
        (".tgs", b"\x1f\x8bdata", "tgs", "application/x-tgsticker"),
        (".webm", b"\x1aE\xdf\xa3data", "webm", "video/webm"),
    ],
)
async def test_only_allowlisted_preview_formats_are_served(
    tmp_path: Path,
    suffix: str,
    content: bytes,
    expected_format: str,
    expected_mime: str,
) -> None:
    telegram_file = FakeTelegramFile(f"emoji/file{suffix}", content)
    bot = FakeBot(
        stickers=[FakeSticker("999")], files={"file-id": telegram_file}
    )
    service = _service(tmp_path / expected_format)

    result = await service.resolve(["999"], client=bot)

    assert result.items[0].preview_format == expected_format
    preview = service.resolve_cached_preview("999")
    assert preview is not None
    assert preview.mime_type == expected_mime
    assert preview.path.suffix == suffix


@pytest.mark.asyncio
async def test_unsupported_invalid_and_oversized_previews_degrade_to_fallback(
    tmp_path: Path,
) -> None:
    cases = [
        (FakeTelegramFile("emoji/file.png", b"PNG"), "unsupported-preview"),
        (FakeTelegramFile("emoji/file.webp", b"not-webp"), "invalid-preview"),
        (
            FakeTelegramFile(
                "emoji/file.webp",
                b"RIFF\x04\x00\x00\x00WEBPdata",
                file_size=101,
            ),
            "preview-too-large",
        ),
    ]
    for index, (telegram_file, reason) in enumerate(cases):
        bot = FakeBot(
            stickers=[FakeSticker(str(index + 1))],
            files={"file-id": telegram_file},
        )
        service = _service(tmp_path / str(index), max_preview_bytes=100)

        result = await service.resolve([str(index + 1)], client=bot)

        assert result.items[0].status == "fallback-only"
        assert result.items[0].reason == reason
        assert result.items[0].preview_key is None
        assert service.resolve_cached_preview(str(index + 1)) is None


@pytest.mark.asyncio
async def test_cached_preview_remains_available_without_a_token(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    bot = FakeBot(
        stickers=[FakeSticker("123")],
        files={
            "file-id": FakeTelegramFile(
                "emoji/file.webp", b"RIFF\x04\x00\x00\x00WEBPdata"
            )
        },
    )
    await _service(cache_root).resolve(["123"], client=bot)

    reloaded = _service(cache_root)
    result = await reloaded.resolve(["123"], bot_token=None)

    assert result.items[0].status == "resolved"
    assert result.items[0].reason == "missing-token"
    assert result.items[0].cached is True
    assert result.items[0].preview_key == "123"


@pytest.mark.asyncio
async def test_missing_token_is_non_blocking_and_does_not_construct_a_bot(
    tmp_path: Path,
) -> None:
    def forbidden_factory(token: str) -> FakeBot:
        raise AssertionError("factory must not run")

    service = _service(tmp_path, bot_factory=forbidden_factory)
    result = await service.resolve(
        ["123"], fallback_by_id={"123": "🧪"}, bot_token="   "
    )

    assert result.items[0].status == "fallback-only"
    assert result.items[0].reason == "missing-token"
    assert result.items[0].fallback_emoji == "🧪"


@pytest.mark.asyncio
async def test_resolved_sticker_replaces_a_cached_default_fallback(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    initial = await service.resolve(["123"])
    assert initial.items[0].fallback_emoji == "🙂"

    bot = FakeBot(
        stickers=[FakeSticker("123", emoji="🎉")],
        files={
            "file-id": FakeTelegramFile(
                "emoji/file.webp", b"RIFF\x04\x00\x00\x00WEBPdata"
            )
        },
    )
    resolved = await service.resolve(["123"], client=bot)
    assert resolved.items[0].fallback_emoji == "🎉"


@pytest.mark.asyncio
async def test_network_errors_and_logs_redact_the_bot_token(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "123456:SUPER-SECRET-TOKEN"
    bot = FakeBot(resolve_error=RuntimeError(f"request URL contained {secret}"))
    service = _service(tmp_path, bot_factory=lambda token: bot)

    with caplog.at_level(logging.WARNING):
        result = await service.resolve(["123"], bot_token=secret)

    assert result.items[0].status == "fallback-only"
    assert result.items[0].reason == "network-error"
    assert bot.shutdowns == 1
    assert secret not in caplog.text
    assert secret not in repr(result)
    assert secret not in (tmp_path / "123.json").read_text("utf-8")


def test_cached_preview_rejects_path_traversal_and_tampered_metadata(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path / "cache")
    for invalid in ("../123", "123/../../secret", "123.webp", "1\\2"):
        with pytest.raises(CustomEmojiRequestError):
            service.resolve_cached_preview(invalid)

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "123.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "id": "123",
                "fallbackEmoji": "🙂",
                "status": "resolved",
                "source": "manual-id",
                "lastUsedAt": "2026-07-29T10:30:00Z",
                "lastCheckedAt": "2026-07-29T10:30:00Z",
                "loadedAt": "2026-07-29T10:30:00Z",
                "previewFormat": "../../secret",
            }
        ),
        encoding="utf-8",
    )
    assert service.resolve_cached_preview("123") is None

    metadata = json.loads((cache / "123.json").read_text(encoding="utf-8"))
    metadata["previewFormat"] = "webp"
    (cache / "123.json").write_text(json.dumps(metadata), encoding="utf-8")
    (cache / "123.webp").write_bytes(b"untrusted-content")
    assert service.resolve_cached_preview("123") is None


@pytest.mark.asyncio
async def test_capability_send_is_explicit_uses_utf16_entity_and_is_not_retried(
    tmp_path: Path,
) -> None:
    bot = FakeBot()
    service = _service(tmp_path)

    pending = await service.test_capability("123", chat_id=None, client=bot)
    assert pending.capability == "test-required"
    assert bot.sent_messages == []

    available = await service.test_capability("123", chat_id=42, client=bot)
    assert available.capability == "available"
    assert len(bot.sent_messages) == 1
    sent = bot.sent_messages[0]
    assert sent["chat_id"] == 42
    assert sent["text"] == "🙂"
    assert sent["disable_notification"] is True
    entity = sent["entities"][0]
    assert entity.type == "custom_emoji"
    assert entity.offset == 0
    assert entity.length == 2
    assert entity.custom_emoji_id == "123"

    class FakeBadRequest(Exception):
        pass

    failing = FakeBot(send_error=FakeBadRequest("not allowed"))
    unavailable = await service.test_capability("123", chat_id=42, client=failing)
    assert unavailable.capability == "unavailable"
    assert unavailable.reason == "capability-unavailable"
    assert len(failing.sent_messages) == 1


@pytest.mark.asyncio
async def test_capability_missing_token_never_sends(tmp_path: Path) -> None:
    service = _service(tmp_path)
    result = await service.test_capability(
        "123", chat_id="@test_chat", bot_token=None
    )
    assert result.to_api_dict() == {
        "capability": "unknown",
        "reason": "missing-token",
    }
