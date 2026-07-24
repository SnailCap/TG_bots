from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app
from tg_bot_core import Actor
from tg_bot_core.store import SqliteStore


def test_users_api_reads_and_updates_the_durable_runtime_registry(tmp_path: Path) -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Users API Bot"},
    ).json()
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    bot_id = json.loads((root / "resources" / "bot.json").read_text(encoding="utf-8"))["id"]

    async def seed_user() -> None:
        store = SqliteStore(root / "data" / "runtime.sqlite3")
        await store.initialize()
        await store.upsert_user(
            bot_id,
            Actor(123456, 77, "ada", "Ada", "Lovelace", language_code="en"),
        )
        await store.update_user_avatar(
            bot_id,
            123456,
            file_id="avatar-v1",
            data=b"avatar-bytes",
            mime_type="image/jpeg",
        )

    asyncio.run(seed_user())

    listed = client.get(f"/api/v1/projects/{project_id}/users")
    assert listed.status_code == 200
    assert listed.json() == [
        {
            "telegram_id": "123456",
            "username": "ada",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "language_code": "en",
            "role": "user",
            "status": "active",
            "note": "",
            "avatar_version": "avatar-v1",
        }
    ]

    updated = client.put(
        f"/api/v1/projects/{project_id}/users/123456",
        json={"role": "administrator", "blocked": True, "note": "Owner"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "administrator"
    assert updated.json()["status"] == "blocked"
    assert updated.json()["note"] == "Owner"

    avatar = client.get(f"/api/v1/projects/{project_id}/users/123456/avatar")
    assert avatar.status_code == 200
    assert avatar.content == b"avatar-bytes"
    assert avatar.headers["content-type"] == "image/jpeg"

    missing = client.put(
        f"/api/v1/projects/{project_id}/users/999",
        json={"role": "user", "blocked": False, "note": ""},
    )
    assert missing.status_code == 404


def test_v3_api_resource_and_handler_contract(tmp_path: Path) -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "API Bot"},
    )
    assert created.status_code == 200
    workspace = created.json()
    project_id = workspace["project_id"]
    assert workspace["schema_version"] == 3
    assert workspace["package"] == "api_bot"
    assert "templates" not in workspace

    home = client.get(f"/api/v1/projects/{project_id}/views/home").json()
    assert home["payload"]["text"] == {"template": "views/home.txt"}
    assert home["text_content"] == "Welcome to your bot!\n"
    assert home["text_revision"]
    home["payload"]["keyboard"] = [
        [{"id": "api_action", "text": "Run", "action": {"type": "noop"}}]
    ]
    missing_text_revision = client.put(
        f"/api/v1/projects/{project_id}/views/home",
        json={
            "payload": home["payload"],
            "revision": home["revision"],
            "text_content": "Missing text revision",
        },
    )
    assert missing_text_revision.status_code == 422
    saved = client.put(
        f"/api/v1/projects/{project_id}/views/home",
        json={
            "payload": home["payload"],
            "revision": home["revision"],
            "text_content": "Updated API text",
            "text_revision": home["text_revision"],
        },
    )
    assert saved.status_code == 200
    saved_view = saved.json()
    assert saved_view["text_content"] == "Updated API text"

    stale = client.put(
        f"/api/v1/projects/{project_id}/views/home",
        json={
            "payload": home["payload"],
            "revision": home["revision"],
            "text_content": "Stale API text",
            "text_revision": home["text_revision"],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "revision_conflict"

    handlers = client.get(f"/api/v1/projects/{project_id}/handlers").json()
    scaffolded = client.post(
        f"/api/v1/projects/{project_id}/handlers",
        json={
            "handler_id": "api.run",
            "kind": "button",
            "registry_revision": handlers["revision"],
            "attachment": {
                "type": "view_button",
                "view_id": "home",
                "button_id": "api_action",
            },
            "target_revision": saved_view["revision"],
        },
    )
    assert scaffolded.status_code == 200
    handler = scaffolded.json()
    assert handler["inspection"]["status"] == "ready"
    assert handler["file_created"] is True

    detail = client.get(
        f"/api/v1/projects/{project_id}/handlers/api.run"
    ).json()
    usages = client.get(
        f"/api/v1/projects/{project_id}/handlers/api.run/usages"
    ).json()
    source = client.post(
        f"/api/v1/projects/{project_id}/handlers/api.run/open"
    ).json()
    assert detail["id"] == "api.run"
    assert usages["usages"][0]["entity_type"] == "view_button"
    assert Path(source["file_path"]).is_file()

    source_path = Path(source["file_path"])
    source_path.unlink()
    missing = client.get(
        f"/api/v1/projects/{project_id}/handlers/api.run"
    )
    assert missing.status_code == 200
    assert missing.json()["inspection"]["status"] == "missing_file"

    repaired = client.post(
        f"/api/v1/projects/{project_id}/handlers/api.run/repair",
        json={"registry_revision": detail["revision"]},
    )
    assert repaired.status_code == 200
    assert repaired.json()["file_created"] is True
    assert repaired.json()["inspection"]["status"] == "ready"
    repaired_source = source_path.read_bytes()

    conflict = client.post(
        f"/api/v1/projects/{project_id}/handlers/api.run/repair",
        json={"registry_revision": detail["revision"]},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "resource_conflict"
    assert source_path.read_bytes() == repaired_source

    commands = client.get(f"/api/v1/projects/{project_id}/commands").json()
    updated_commands = client.put(
        f"/api/v1/projects/{project_id}/commands",
        json={
            "payload": {
                "commands": [
                    {
                        "name": "help",
                        "action": {"type": "view.render", "target": "home"},
                    }
                ]
            },
            "revision": commands["revision"],
        },
    )
    assert updated_commands.status_code == 200

    flow = client.post(
        f"/api/v1/projects/{project_id}/flows",
        json={
            "id": "secondary",
            "payload": {
                "initial_state": "start",
                "lifecycle": {},
                "states": {"start": {"view": "home", "events": {}}},
            },
        },
    )
    assert flow.status_code == 200
    assert any(
        item["id"] == "secondary"
        for item in client.get(f"/api/v1/projects/{project_id}/flows").json()
    )

    validation = client.get(
        f"/api/v1/projects/{project_id}/validation"
    ).json()
    assert not [item for item in validation["issues"] if item["level"] == "error"]


def test_resource_rename_routes_cover_studio_named_resources(tmp_path: Path) -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/projects", json={"parent_path": str(tmp_path), "name": "Rename API Bot"}
    ).json()
    project_id = workspace["project_id"]

    view = client.get(f"/api/v1/projects/{project_id}/views/home").json()
    renamed_view = client.post(
        f"/api/v1/projects/{project_id}/views/home/rename",
        json={"id": "welcome", "revision": view["revision"]},
    )
    assert renamed_view.status_code == 200
    assert renamed_view.json()["id"] == "welcome"

    flow = client.get(f"/api/v1/projects/{project_id}/flows/home").json()
    renamed_flow = client.post(
        f"/api/v1/projects/{project_id}/flows/home/rename",
        json={"id": "launch", "revision": flow["revision"]},
    )
    assert renamed_flow.status_code == 200
    assert renamed_flow.json()["id"] == "launch"

    assert client.get(f"/api/v1/projects/{project_id}/templates/home.txt").status_code == 404

    handlers = client.get(f"/api/v1/projects/{project_id}/handlers").json()
    handler = client.post(
        f"/api/v1/projects/{project_id}/handlers",
        json={"handler_id": "api.run", "kind": "task", "registry_revision": handlers["revision"]},
    )
    assert handler.status_code == 200, handler.text

    schedule = client.post(
        f"/api/v1/projects/{project_id}/schedules",
        json={"id": "daily", "payload": {"handler": "api.run", "trigger": {"type": "interval", "seconds": 60}, "payload": {}}},
    ).json()
    renamed_schedule = client.post(
        f"/api/v1/projects/{project_id}/schedules/daily/rename",
        json={"id": "nightly", "revision": schedule["revision"]},
    )
    assert renamed_schedule.status_code == 200
    assert renamed_schedule.json()["id"] == "nightly"

    renamed_handler = client.post(
        f"/api/v1/projects/{project_id}/handlers/api.run/rename",
        json={"id": "api.execute", "revision": handler.json()["revision"]},
    )
    assert renamed_handler.status_code == 200
    assert renamed_handler.json()["id"] == "api.execute"


def test_project_settings_store_a_redacted_runtime_token(tmp_path: Path) -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Settings Bot"},
    ).json()
    project_id = workspace["project_id"]

    initial = client.get(f"/api/v1/projects/{project_id}/settings")
    assert initial.status_code == 200
    assert initial.json() == {"telegram_bot_token_configured": False, "revision": None}

    saved = client.put(
        f"/api/v1/projects/{project_id}/settings",
        json={"telegram_bot_token": "123456:project_token", "revision": None},
    )
    assert saved.status_code == 200
    assert saved.json()["telegram_bot_token_configured"] is True
    assert saved.json()["revision"]
    assert "project_token" not in saved.text
    environment_path = Path(workspace["project_root"]) / ".env"
    assert environment_path.read_text(encoding="utf-8") == "BOT_TOKEN=123456:project_token\n"

    stale = client.put(
        f"/api/v1/projects/{project_id}/settings",
        json={"clear_telegram_bot_token": True, "revision": None},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "revision_conflict"

    current = client.get(f"/api/v1/projects/{project_id}/settings").json()
    environment_path.write_text("OTHER=value\nBOT_TOKEN=123456:project_token\n", encoding="utf-8")
    current = client.get(f"/api/v1/projects/{project_id}/settings").json()
    cleared = client.put(
        f"/api/v1/projects/{project_id}/settings",
        json={"clear_telegram_bot_token": True, "revision": current["revision"]},
    )
    assert cleared.status_code == 200
    assert cleared.json()["telegram_bot_token_configured"] is False
    assert environment_path.read_text(encoding="utf-8") == "OTHER=value\n"


def test_handler_detail_reports_keyword_only_argument_as_invalid_signature(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Signature Bot"},
    ).json()
    project_id = workspace["project_id"]
    handlers = client.get(f"/api/v1/projects/{project_id}/handlers").json()
    scaffolded = client.post(
        f"/api/v1/projects/{project_id}/handlers",
        json={
            "handler_id": "message.inspect",
            "kind": "message",
            "registry_revision": handlers["revision"],
        },
    )
    assert scaffolded.status_code == 200
    source = Path(scaffolded.json()["open_target"]["file_path"])
    source.write_text(
        "from tg_bot_core import HandlerResult, MessageContext\n\n\n"
        "async def handle(\n"
        "    ctx: MessageContext, *, audit: bool = False\n"
        ") -> HandlerResult:\n"
        "    return HandlerResult.success()\n",
        encoding="utf-8",
    )

    detail = client.get(
        f"/api/v1/projects/{project_id}/handlers/message.inspect"
    )
    assert detail.status_code == 200
    assert detail.json()["inspection"]["status"] == "invalid_signature"
    validation = client.get(
        f"/api/v1/projects/{project_id}/validation"
    ).json()["issues"]
    assert any(issue["code"] == "handler_signature_invalid" for issue in validation)
