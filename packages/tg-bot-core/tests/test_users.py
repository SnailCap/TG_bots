from __future__ import annotations

from pathlib import Path

import pytest

from tg_bot_core import Actor, BotApp, BotConfig, CommandEvent
from tg_bot_core.store import SqliteStore
from tg_bot_core.transport import UserProfileAvatar

from conftest import FakeTransport, make_project


@pytest.mark.asyncio
async def test_user_registry_preserves_managed_fields_and_avatar_across_restarts(
    tmp_path: Path,
) -> None:
    database = tmp_path / "data" / "runtime.sqlite3"
    store = SqliteStore(database)
    await store.initialize()

    original = await store.upsert_user(
        "bot-one",
        Actor(42, 7, "ada", "Ada", "Lovelace", language_code="en"),
    )
    assert original.role == "user"
    await store.update_user(
        "bot-one", 42, role="moderator", blocked=True, note="Internal note"
    )
    await store.update_user_avatar(
        "bot-one",
        42,
        file_id="telegram-photo-v1",
        data=b"profile-photo",
        mime_type="image/jpeg",
    )

    restarted = SqliteStore(database)
    await restarted.initialize()
    refreshed = await restarted.upsert_user(
        "bot-one",
        Actor(42, 9, "ada_new", "Augusta", "King", language_code="fr"),
    )

    assert (
        refreshed.username,
        refreshed.first_name,
        refreshed.last_name,
        refreshed.language_code,
    ) == ("ada_new", "Augusta", "King", "fr")
    assert (refreshed.role, refreshed.blocked, refreshed.note) == (
        "moderator",
        True,
        "Internal note",
    )
    assert refreshed.avatar_file_id == "telegram-photo-v1"
    avatar = await restarted.get_user_avatar("bot-one", 42)
    assert avatar is not None
    assert (avatar.data, avatar.mime_type) == (b"profile-photo", "image/jpeg")


class AvatarTransport(FakeTransport):
    async def fetch_user_avatar(
        self, user_id: int, current_file_id: str | None
    ) -> UserProfileAvatar:
        assert user_id == 42
        if current_file_id == "photo-v1":
            return UserProfileAvatar("photo-v1")
        return UserProfileAvatar("photo-v1", b"photo", "image/jpeg")


@pytest.mark.asyncio
async def test_runtime_applies_roles_refreshes_avatar_and_ignores_blocked_users(
    tmp_path: Path,
) -> None:
    make_project(tmp_path)
    transport = AvatarTransport()
    app = BotApp(
        config=BotConfig(
            project_root=tmp_path,
            token=None,
            database_path=tmp_path / "data" / "runtime.sqlite3",
        ),
        transport=transport,
    )
    await app.start()
    actor = Actor(42, 7, "ada", "Ada", "Lovelace")
    await app.store.upsert_user("fixture-bot", actor)
    await app.store.update_user(
        "fixture-bot", 42, role="trusted", blocked=False, note=""
    )
    assert app.dispatcher is not None
    seen_roles: list[str] = []

    async def capture_role(_session, event) -> None:
        seen_roles.append(event.actor.role)

    app.dispatcher.dispatch = capture_role  # type: ignore[method-assign]
    await transport.emit(CommandEvent(actor, 1, "start"))
    assert seen_roles == ["trusted"]
    avatar = await app.store.get_user_avatar("fixture-bot", 42)
    assert avatar is not None and avatar.data == b"photo"

    await app.store.update_user(
        "fixture-bot", 42, role="trusted", blocked=True, note=""
    )
    await transport.emit(CommandEvent(actor, 2, "start"))
    assert seen_roles == ["trusted"]
    await app.stop()
