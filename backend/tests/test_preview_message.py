from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.workspace.preview_message import (
    PreviewMessageCompileError,
    PreviewMessageConfigurationError,
    PreviewMessageSender,
)
from app.workspace.service import ProjectService


@dataclass
class FakeSentMessage:
    message_id: int


class FakePreviewBot:
    def __init__(self, *, fail_at: int | None = None, secret: str = "") -> None:
        self.fail_at = fail_at
        self.secret = secret
        self.calls: list[dict[str, Any]] = []
        self.initialized = 0
        self.shutdowns = 0
        self.in_flight = False

    async def initialize(self) -> None:
        self.initialized += 1

    async def shutdown(self) -> None:
        self.shutdowns += 1

    async def send_message(self, **kwargs: Any) -> FakeSentMessage:
        assert not self.in_flight, "preview chunks must be sent sequentially"
        self.in_flight = True
        try:
            await asyncio.sleep(0)
            index = len(self.calls)
            self.calls.append(kwargs)
            if self.fail_at == index:
                raise RuntimeError(
                    f"Telegram request failed at https://api.telegram.org/bot{self.secret}"
                )
            return FakeSentMessage(1000 + index)
        finally:
            self.in_flight = False


def content_document(*, long: bool = False, variable: bool = False) -> dict[str, Any]:
    if variable:
        blocks = [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "variable",
                        "variableReference": {"path": "user.first_name"},
                        "marks": [{"type": "bold"}],
                    }
                ],
            }
        ]
    elif long:
        blocks = [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "A" * 3000,
                        "marks": [{"type": "bold"}],
                    }
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "B" * 3000,
                        "marks": [{"type": "italic"}],
                    }
                ],
            },
        ]
    else:
        blocks = [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": "Preview",
                        "marks": [{"type": "bold"}],
                    }
                ],
            }
        ]
    return {
        "schemaVersion": 1,
        "id": "preview",
        "content": blocks,
        "metadata": {
            "createdAt": "2026-07-29T00:00:00Z",
            "updatedAt": "2026-07-29T00:00:00Z",
            "editorVersion": "1.0.0",
            "source": "botstudio",
        },
    }


def create_project(
    service: ProjectService, tmp_path: Path, *, token: str | None
) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    workspace = service.create_starter(
        parent_path=str(tmp_path), name="Preview Sender"
    )
    project_id = workspace["project_id"]
    if token is not None:
        service.save_project_settings(
            project_id,
            telegram_bot_token=token,
            clear_telegram_bot_token=False,
            revision=None,
        )
    return project_id


def test_send_preview_uses_project_token_and_exact_compiler_chunks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BOT_TOKEN", "process-token-must-not-be-used")
    bot = FakePreviewBot()
    factory_tokens: list[str] = []

    def factory(token: str) -> FakePreviewBot:
        factory_tokens.append(token)
        return bot

    service = ProjectService(
        preview_message_sender=PreviewMessageSender(bot_factory=factory)
    )
    token = "123456:project-preview-secret"
    project_id = create_project(service, tmp_path, token=token)
    document = content_document(long=True)
    compiled = service.compile_content(
        project_id,
        document,
        variables={},
        split_long_messages=True,
    )

    result = asyncio.run(
        service.send_preview_message(
            project_id,
            document,
            variables={},
            chat_id="  @preview_chat  ",
            split_long_messages=True,
        )
    )

    assert factory_tokens == [token]
    assert bot.initialized == 1
    assert bot.shutdowns == 1
    assert result == {
        "sent": True,
        "sentCount": 2,
        "totalCount": 2,
        "messageIds": [1000, 1001],
        "warnings": compiled["warnings"],
    }
    assert len(bot.calls) == len(compiled["messages"]) == 2
    for call, expected in zip(bot.calls, compiled["messages"], strict=True):
        assert call["chat_id"] == "@preview_chat"
        assert call["text"] == expected["text"]
        assert call["disable_notification"] is True
        assert "parse_mode" not in call
        assert [
            {
                "type": entity.type,
                "offset": entity.offset,
                "length": entity.length,
                **({"url": entity.url} if entity.url is not None else {}),
                **(
                    {"language": entity.language}
                    if entity.language is not None
                    else {}
                ),
                **(
                    {"custom_emoji_id": entity.custom_emoji_id}
                    if entity.custom_emoji_id is not None
                    else {}
                ),
            }
            for entity in call["entities"]
        ] == expected["entities"]
    assert token not in str(result)
    assert "process-token-must-not-be-used" not in str(result)


def test_compiler_errors_and_missing_project_token_never_create_a_bot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory_tokens: list[str] = []

    def factory(token: str) -> FakePreviewBot:
        factory_tokens.append(token)
        return FakePreviewBot()

    sender = PreviewMessageSender(bot_factory=factory)
    configured = ProjectService(preview_message_sender=sender)
    configured_id = create_project(
        configured,
        tmp_path / "configured",
        token="123456:configured-secret",
    )
    with pytest.raises(PreviewMessageCompileError) as compile_error:
        asyncio.run(
            configured.send_preview_message(
                configured_id,
                content_document(variable=True),
                variables={},
                chat_id=123,
            )
        )
    assert compile_error.value.diagnostics[0].code == "variable_resolution"
    assert factory_tokens == []

    monkeypatch.setenv("BOT_TOKEN", "process-token-must-not-be-used")
    unconfigured = ProjectService(preview_message_sender=sender)
    unconfigured_id = create_project(
        unconfigured,
        tmp_path / "unconfigured",
        token=None,
    )
    with pytest.raises(PreviewMessageConfigurationError):
        asyncio.run(
            unconfigured.send_preview_message(
                unconfigured_id,
                content_document(),
                variables={},
                chat_id=123,
            )
        )
    assert factory_tokens == []


def test_send_preview_api_returns_typed_result_and_safe_partial_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    token = "123456:api-preview-secret"
    success_bot = FakePreviewBot()
    service = ProjectService(
        preview_message_sender=PreviewMessageSender(
            bot_factory=lambda supplied: success_bot
        )
    )
    app = create_app()
    app.state.project_service = service
    client = TestClient(app)
    created = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Preview API"},
    )
    project_id = created.json()["project_id"]
    settings = client.put(
        f"/api/v1/projects/{project_id}/settings",
        json={"telegram_bot_token": token},
    )
    assert settings.status_code == 200

    sent = client.post(
        f"/api/v1/projects/{project_id}/content/send-preview",
        json={
            "document": content_document(long=True),
            "variables": {},
            "chatId": "@preview_chat",
            "splitLongMessages": True,
        },
    )
    assert sent.status_code == 200
    assert sent.json() == {
        "sent": True,
        "sentCount": 2,
        "totalCount": 2,
        "messageIds": [1000, 1001],
        "warnings": [
            {
                "severity": "warning",
                "code": "message_split",
                "message": "Rendered content was split into 2 Telegram messages.",
                "path": None,
            }
        ],
    }
    assert token not in sent.text

    failing_bot = FakePreviewBot(fail_at=1, secret=token)
    service.preview_message_sender = PreviewMessageSender(
        bot_factory=lambda supplied: failing_bot
    )
    with caplog.at_level(logging.WARNING):
        failed = client.post(
            f"/api/v1/projects/{project_id}/content/send-preview",
            json={
                "document": content_document(long=True),
                "variables": {},
                "chatId": 123,
                "splitLongMessages": True,
            },
        )

    assert failed.status_code == 502
    assert failed.json()["detail"] == {
        "code": "telegram_preview_send_failed",
        "message": "Telegram could not deliver the preview message. Sent 1 of 2 chunks.",
        "sentCount": 1,
        "totalCount": 2,
    }
    assert failing_bot.shutdowns == 1
    assert token not in failed.text
    assert token not in caplog.text


def test_send_preview_api_blocks_compiler_errors_before_delivery(
    tmp_path: Path,
) -> None:
    bot = FakePreviewBot()
    service = ProjectService(
        preview_message_sender=PreviewMessageSender(bot_factory=lambda token: bot)
    )
    app = create_app()
    app.state.project_service = service
    client = TestClient(app)
    project_id = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Compiler Guard"},
    ).json()["project_id"]
    client.put(
        f"/api/v1/projects/{project_id}/settings",
        json={"telegram_bot_token": "123456:compiler-secret"},
    )

    response = client.post(
        f"/api/v1/projects/{project_id}/content/send-preview",
        json={
            "document": content_document(long=True),
            "variables": {},
            "chatId": 123,
            "splitLongMessages": False,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "content_compile_failed"
    assert response.json()["detail"]["errors"][0]["code"] == "message_too_long"
    assert bot.initialized == 0
    assert bot.calls == []
