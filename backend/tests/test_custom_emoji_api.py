from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.workspace.custom_emoji import (
    CachedCustomEmojiPreview,
    CustomEmojiCapabilityResult,
    CustomEmojiItem,
    CustomEmojiResolveResult,
    CustomEmojiService,
    CustomEmojiSource,
    validate_custom_emoji_ids,
)
from app.workspace.service import ProjectService


class StubCustomEmojiService:
    def __init__(self) -> None:
        self.resolve_calls: list[dict[str, Any]] = []
        self.capability_calls: list[dict[str, Any]] = []
        self.previews: dict[str, CachedCustomEmojiPreview] = {}

    async def resolve(
        self,
        custom_emoji_ids: list[str],
        *,
        bot_token: str | None = None,
        client: object | None = None,
        fallback_by_id: dict[str, str] | None = None,
        source: CustomEmojiSource = "manual-id",
    ) -> CustomEmojiResolveResult:
        del client
        ids = validate_custom_emoji_ids(custom_emoji_ids)
        self.resolve_calls.append(
            {
                "ids": ids,
                "bot_token": bot_token,
                "fallback_by_id": fallback_by_id,
                "source": source,
            }
        )
        fallbacks = fallback_by_id or {}
        return CustomEmojiResolveResult(
            tuple(
                CustomEmojiItem(
                    id=custom_emoji_id,
                    fallback_emoji=fallbacks.get(custom_emoji_id, "🙂"),
                    status="fallback-only",
                    source=source,
                    last_used_at="2026-07-29T12:00:00Z",
                    last_checked_at="2026-07-29T12:00:00Z",
                )
                for custom_emoji_id in ids
            )
        )

    def resolve_cached_preview(
        self, custom_emoji_id: str
    ) -> CachedCustomEmojiPreview | None:
        validate_custom_emoji_ids([custom_emoji_id])
        return self.previews.get(custom_emoji_id)

    async def test_capability(
        self,
        custom_emoji_id: str,
        *,
        chat_id: int | str | None,
        bot_token: str | None = None,
        client: object | None = None,
        fallback_emoji: str = "🙂",
    ) -> CustomEmojiCapabilityResult:
        del client
        validate_custom_emoji_ids([custom_emoji_id])
        self.capability_calls.append(
            {
                "id": custom_emoji_id,
                "chat_id": chat_id,
                "bot_token": bot_token,
                "fallback_emoji": fallback_emoji,
            }
        )
        return CustomEmojiCapabilityResult("available")


def _project_service(stub: StubCustomEmojiService) -> ProjectService:
    return ProjectService(
        custom_emoji_service=cast(CustomEmojiService, stub)
    )


def test_project_service_uses_only_the_project_env_token(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "process-env-token-must-not-be-used")
    stub = StubCustomEmojiService()
    project_service = _project_service(stub)
    workspace = project_service.create_starter(
        parent_path=str(tmp_path), name="Custom Emoji Service"
    )
    project_id = workspace["project_id"]

    without_project_token = asyncio.run(
        project_service.resolve_custom_emojis(project_id, ["123"])
    )
    assert stub.resolve_calls[-1]["bot_token"] is None
    assert "process-env-token-must-not-be-used" not in str(without_project_token)

    settings = project_service.save_project_settings(
        project_id,
        telegram_bot_token="123456:project-secret",
        clear_telegram_bot_token=False,
        revision=None,
    )
    with_project_token = asyncio.run(
        project_service.resolve_custom_emojis(
            project_id,
            ["123"],
            fallback_by_id={"123": "👍"},
            source="favorite",
        )
    )

    assert settings == {
        "telegram_bot_token_configured": True,
        "revision": settings["revision"],
    }
    assert stub.resolve_calls[-1] == {
        "ids": ("123",),
        "bot_token": "123456:project-secret",
        "fallback_by_id": {"123": "👍"},
        "source": "favorite",
    }
    assert "123456:project-secret" not in str(with_project_token)


def test_custom_emoji_api_resolves_tests_and_serves_cached_preview(
    tmp_path: Path,
) -> None:
    stub = StubCustomEmojiService()
    project_service = _project_service(stub)
    app = create_app()
    app.state.project_service = project_service
    client = TestClient(app)

    created = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Custom Emoji API"},
    )
    assert created.status_code == 200
    project_id = created.json()["project_id"]

    settings = client.put(
        f"/api/v1/projects/{project_id}/settings",
        json={"telegram_bot_token": "123456:api-secret"},
    )
    assert settings.status_code == 200
    assert "api-secret" not in settings.text

    resolved = client.post(
        f"/api/v1/projects/{project_id}/telegram/custom-emojis/resolve",
        json={
            "customEmojiIds": ["111", "111", "222"],
            "fallbackById": {"111": "🎉"},
            "source": "recent",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["items"] == [
        {
            "id": "111",
            "fallbackEmoji": "🎉",
            "status": "fallback-only",
            "source": "recent",
            "lastUsedAt": "2026-07-29T12:00:00Z",
            "lastCheckedAt": "2026-07-29T12:00:00Z",
            "cached": False,
        },
        {
            "id": "222",
            "fallbackEmoji": "🙂",
            "status": "fallback-only",
            "source": "recent",
            "lastUsedAt": "2026-07-29T12:00:00Z",
            "lastCheckedAt": "2026-07-29T12:00:00Z",
            "cached": False,
        },
    ]
    assert "api-secret" not in resolved.text
    assert stub.resolve_calls[-1]["bot_token"] == "123456:api-secret"

    capability = client.post(
        f"/api/v1/projects/{project_id}/telegram/custom-emojis/capability-test",
        json={
            "customEmojiId": "111",
            "chatId": "@preview_chat",
            "fallbackEmoji": "🎉",
        },
    )
    assert capability.status_code == 200
    assert capability.json() == {"capability": "available"}
    assert stub.capability_calls[-1] == {
        "id": "111",
        "chat_id": "@preview_chat",
        "bot_token": "123456:api-secret",
        "fallback_emoji": "🎉",
    }

    preview_path = tmp_path / "preview.webp"
    preview_bytes = b"RIFF\x04\x00\x00\x00WEBP"
    preview_path.write_bytes(preview_bytes)
    stub.previews["111"] = CachedCustomEmojiPreview(
        path=preview_path.resolve(), mime_type="image/webp"
    )
    preview = client.get(
        f"/api/v1/projects/{project_id}/telegram/custom-emojis/111/preview"
    )
    assert preview.status_code == 200
    assert preview.content == preview_bytes
    assert preview.headers["content-type"] == "image/webp"
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert str(preview_path) not in str(preview.headers)


def test_custom_emoji_api_maps_invalid_requests_and_missing_previews(
    tmp_path: Path,
) -> None:
    stub = StubCustomEmojiService()
    project_service = _project_service(stub)
    app = create_app()
    app.state.project_service = project_service
    client = TestClient(app)
    project_id = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Custom Emoji Errors"},
    ).json()["project_id"]

    invalid = client.post(
        f"/api/v1/projects/{project_id}/telegram/custom-emojis/resolve",
        json={"ids": ["../../secrets"]},
    )
    assert invalid.status_code == 422
    assert invalid.json() == {
        "detail": {
            "code": "invalid_custom_emoji_request",
            "message": "Every custom emoji ID must be an ASCII decimal string.",
        }
    }

    missing = client.get(
        f"/api/v1/projects/{project_id}/telegram/custom-emojis/123/preview"
    )
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "resource_not_found"

