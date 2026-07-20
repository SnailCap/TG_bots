from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.app import create_app


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

    home = client.get(f"/api/v1/projects/{project_id}/views/home").json()
    home["payload"]["keyboard"] = [
        [{"id": "api_action", "text": "Run", "action": {"type": "noop"}}]
    ]
    saved = client.put(
        f"/api/v1/projects/{project_id}/views/home",
        json={"payload": home["payload"], "revision": home["revision"]},
    )
    assert saved.status_code == 200
    saved_view = saved.json()

    stale = client.put(
        f"/api/v1/projects/{project_id}/views/home",
        json={"payload": home["payload"], "revision": home["revision"]},
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
