from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.workspace import ProjectService
from app.workspace.repository import ResourceConflict, WorkspaceError
from app.workspace.service import RevisionConflict


def content_document(document_id: str, text: str = "Hello ") -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "id": document_id,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": text, "marks": [{"type": "bold"}]},
                    {
                        "type": "variable",
                        "variableReference": {
                            "fieldId": "core.user.first_name",
                            "path": "user.first_name",
                            "source": "{{ user.first_name }}",
                        },
                        "marks": [{"type": "bold"}],
                    },
                    {"type": "text", "text": " "},
                    {
                        "type": "customEmoji",
                        "customEmojiId": "5368324170671202286",
                        "fallbackEmoji": "🙂",
                    },
                ],
            }
        ],
        "metadata": {
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "editorVersion": "1.0.0",
            "source": "botstudio",
        },
    }


def test_rich_view_content_is_revisioned_backed_up_and_lifecycle_safe(
    tmp_path: Path,
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Content Bot")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    legacy = service.get_view(project_id, "home")
    assert legacy["content_document"] is None
    assert legacy["content_revision"] is None

    saved = service.save_view_content(
        project_id,
        "home",
        legacy["payload"],
        legacy["revision"],
        document=content_document("home"),
        document_revision=None,
        text_revision=legacy["text_revision"],
    )

    assert saved["content_document"]["schemaVersion"] == 1
    assert saved["content_revision"]
    assert saved["payload"]["text"] == {
        "template": "views/home.txt",
        "document": "views/home.json",
    }
    assert (root / "resources/content/views/home.json").is_file()
    assert (root / "resources/templates/views/home.txt").read_text(encoding="utf-8") == (
        "Hello {{ user.first_name }} 🙂"
    )
    backups = list((root / ".botstudio/backups/content/home").glob("*.txt"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == legacy["text_content"]

    with pytest.raises(RevisionConflict):
        service.save_view_content(
            project_id,
            "home",
            legacy["payload"],
            legacy["revision"],
            document=content_document("home", "Stale "),
            document_revision=None,
            text_revision=legacy["text_revision"],
        )

    created = service.create_view(
        project_id,
        "standalone",
        {},
        content_document=content_document("standalone", "Standalone "),
    )
    renamed = service.rename_view(
        project_id, "standalone", "renamed", created["revision"]
    )
    assert renamed["content_document"]["id"] == "renamed"
    assert not (root / "resources/content/views/standalone.json").exists()
    assert (root / "resources/content/views/renamed.json").is_file()
    service.delete_view(project_id, "renamed", renamed["revision"])
    assert not (root / "resources/content/views/renamed.json").exists()
    assert not (root / "resources/templates/views/renamed.txt").exists()


def test_compact_edit_backs_up_and_removes_owned_document_then_recovers_orphan(
    tmp_path: Path,
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Content Lifecycle")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    document_path = root / "resources/content/views/home.json"
    backup_dir = root / ".botstudio/backups/content/home"

    legacy = service.get_view(project_id, "home")
    initial_document = content_document("home", "Initial rich ")
    rich = service.save_view_content(
        project_id,
        "home",
        legacy["payload"],
        legacy["revision"],
        document=initial_document,
        document_revision=None,
        text_revision=legacy["text_revision"],
    )

    compact = service.save_view(
        project_id,
        "home",
        rich["payload"],
        rich["revision"],
        text_content="Edited in compact editor",
        text_revision=rich["text_revision"],
    )

    assert compact["payload"]["text"] == {"template": "views/home.txt"}
    assert compact["content_document"] is None
    assert not document_path.exists()
    json_backups = sorted(backup_dir.glob("*.json"))
    assert len(json_backups) == 1
    assert json.loads(json_backups[0].read_text(encoding="utf-8")) == initial_document

    # Reproduce the orphan left by Studio versions that removed text.document
    # without deleting the canonical document file.
    orphan_document = content_document("home", "Old orphan ")
    service.repository.atomic_write_json(document_path, orphan_document)
    replacement_document = content_document("home", "Recovered rich ")

    recovered = service.save_view_content(
        project_id,
        "home",
        compact["payload"],
        compact["revision"],
        document=replacement_document,
        document_revision=None,
        text_revision=compact["text_revision"],
    )

    assert recovered["content_document"] == replacement_document
    assert json.loads(document_path.read_text(encoding="utf-8")) == replacement_document
    backed_up_documents = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(backup_dir.glob("*.json"))
    ]
    assert backed_up_documents == [initial_document, orphan_document]


def test_rich_migration_backs_up_legacy_inline_text(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Inline Migration")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    inline_path = root / "resources/views/inline.json"
    inline_source = "Legacy inline {{ user.first_name }}"
    service.repository.atomic_write_json(
        inline_path,
        {
            "schema_version": 3,
            "id": "inline",
            "text": {"inline": inline_source},
            "keyboard": [],
        },
    )
    legacy = service.get_view(project_id, "inline")

    saved = service.save_view_content(
        project_id,
        "inline",
        legacy["payload"],
        legacy["revision"],
        document=content_document("inline", "Migrated "),
        document_revision=None,
        text_revision=None,
    )

    assert saved["payload"]["text"] == {
        "template": "views/inline.txt",
        "document": "views/inline.json",
    }
    backups = list((root / ".botstudio/backups/content/inline").glob("*.txt"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == inline_source


def test_compact_edit_does_not_touch_document_referenced_by_another_view(
    tmp_path: Path,
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Shared Content")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    document_path = root / "resources/content/views/home.json"

    legacy = service.get_view(project_id, "home")
    rich = service.save_view_content(
        project_id,
        "home",
        legacy["payload"],
        legacy["revision"],
        document=content_document("home", "Shared rich "),
        document_revision=None,
        text_revision=legacy["text_revision"],
    )
    shared = service.create_view(
        project_id,
        "shared",
        {},
        text_content="Shared fallback",
    )
    shared_path = root / "resources/views/shared.json"
    shared_payload = dict(shared["payload"])
    shared_payload["text"] = {
        "template": "views/shared.txt",
        "document": "views/home.json",
    }
    service.repository.atomic_write_json(shared_path, shared_payload)
    before_document = document_path.read_bytes()

    compact = service.save_view(
        project_id,
        "home",
        rich["payload"],
        rich["revision"],
        text_content="Home compact text",
        text_revision=rich["text_revision"],
    )

    assert document_path.read_bytes() == before_document
    assert not list((root / ".botstudio/backups/content/home").glob("*.json"))
    with pytest.raises(ResourceConflict, match="used by another view"):
        service.save_view_content(
            project_id,
            "home",
            compact["payload"],
            compact["revision"],
            document=content_document("home", "Must not overwrite "),
            document_revision=None,
            text_revision=compact["text_revision"],
        )
    assert document_path.read_bytes() == before_document


def test_rename_view_preserves_document_referenced_by_another_view(
    tmp_path: Path,
) -> None:
    service, project_id, root, owned = _project_with_shared_content_document(
        tmp_path,
        "Shared Rename",
    )
    source_document = root / "resources/content/views/owned.json"
    target_document = root / "resources/content/views/renamed.json"
    before_document = source_document.read_bytes()

    renamed = service.rename_view(
        project_id,
        "owned",
        "renamed",
        owned["revision"],
    )

    assert source_document.read_bytes() == before_document
    assert target_document.is_file()
    assert renamed["payload"]["text"]["document"] == "views/renamed.json"
    assert renamed["content_document"]["id"] == "renamed"
    shared = service.get_view(project_id, "shared")
    assert shared["payload"]["text"]["document"] == "views/owned.json"
    assert shared["content_document"] == json.loads(before_document)


def test_delete_view_preserves_document_referenced_by_another_view(
    tmp_path: Path,
) -> None:
    service, project_id, root, owned = _project_with_shared_content_document(
        tmp_path,
        "Shared Delete",
    )
    document_path = root / "resources/content/views/owned.json"
    before_document = document_path.read_bytes()

    service.delete_view(project_id, "owned", owned["revision"])

    assert document_path.read_bytes() == before_document
    assert not (root / "resources/views/owned.json").exists()
    shared = service.get_view(project_id, "shared")
    assert shared["payload"]["text"]["document"] == "views/owned.json"
    assert shared["content_document"] == json.loads(before_document)


def test_compact_edit_rolls_back_owned_document_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Content Rollback")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    view_path = root / "resources/views/home.json"
    template_path = root / "resources/templates/views/home.txt"
    document_path = root / "resources/content/views/home.json"

    legacy = service.get_view(project_id, "home")
    rich = service.save_view_content(
        project_id,
        "home",
        legacy["payload"],
        legacy["revision"],
        document=content_document("home", "Rollback rich "),
        document_revision=None,
        text_revision=legacy["text_revision"],
    )
    before = {
        path: path.read_bytes()
        for path in (view_path, template_path, document_path)
    }
    original_load = service._load
    load_calls = 0

    def fail_validation_after_writes(workspace):
        nonlocal load_calls
        load_calls += 1
        if load_calls == 2:
            raise WorkspaceError("simulated post-write validation failure")
        return original_load(workspace)

    monkeypatch.setattr(service, "_load", fail_validation_after_writes)
    with pytest.raises(WorkspaceError, match="simulated post-write"):
        service.save_view(
            project_id,
            "home",
            rich["payload"],
            rich["revision"],
            text_content="Compact text that must roll back",
            text_revision=rich["text_revision"],
        )

    assert {path: path.read_bytes() for path in before} == before
    restored = service.get_view(project_id, "home")
    assert restored["payload"]["text"]["document"] == "views/home.json"
    assert restored["content_document"] == rich["content_document"]


def test_content_api_save_and_preview_share_the_compiler(tmp_path: Path) -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/projects",
        json={"parent_path": str(tmp_path), "name": "Content API Bot"},
    ).json()
    project_id = workspace["project_id"]
    detail = client.get(f"/api/v1/projects/{project_id}/views/home").json()
    document = content_document("home")

    compiled = client.post(
        f"/api/v1/projects/{project_id}/content/compile",
        json={"document": document, "variables": {"user": {"first_name": "Ada"}}},
    )
    assert compiled.status_code == 200
    assert compiled.json()["messages"] == [
        {
            "text": "Hello Ada 🙂",
            "entities": [
                {"type": "bold", "offset": 0, "length": 9},
                {
                    "type": "custom_emoji",
                    "offset": 10,
                    "length": 2,
                    "custom_emoji_id": "5368324170671202286",
                },
            ],
        }
    ]

    saved = client.put(
        f"/api/v1/projects/{project_id}/views/home/content",
        json={
            "payload": detail["payload"],
            "revision": detail["revision"],
            "document": document,
            "document_revision": None,
            "text_revision": detail["text_revision"],
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["content_document"] == document
    stored = json.loads(
        (Path(workspace["project_root"]) / "resources/content/views/home.json").read_text(
            encoding="utf-8"
        )
    )
    assert stored == document

    stale = client.put(
        f"/api/v1/projects/{project_id}/views/home/content",
        json={
            "payload": detail["payload"],
            "revision": detail["revision"],
            "document": document,
            "document_revision": None,
            "text_revision": detail["text_revision"],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "revision_conflict"


def _project_with_shared_content_document(
    tmp_path: Path,
    project_name: str,
) -> tuple[ProjectService, str, Path, dict[str, Any]]:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name=project_name)
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    owned = service.create_view(
        project_id,
        "owned",
        {},
        content_document=content_document("owned", "Shared rich "),
    )
    shared = service.create_view(
        project_id,
        "shared",
        {},
        text_content="Shared fallback",
    )
    shared_payload = dict(shared["payload"])
    shared_payload["text"] = {
        "template": "views/shared.txt",
        "document": "views/owned.json",
    }
    service.repository.atomic_write_json(
        root / "resources/views/shared.json",
        shared_payload,
    )
    return service, project_id, root, owned
