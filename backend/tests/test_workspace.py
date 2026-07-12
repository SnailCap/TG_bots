from __future__ import annotations

import compileall
import importlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.workspace.service import RevisionConflict, WorkspaceError, WorkspaceManager


def v2_resources(root: Path) -> Path:
    resources = root / "resources"
    (resources / "views").mkdir(parents=True)
    (resources / "templates").mkdir()
    (resources / "bot.json").write_text(json.dumps({"schema_version": 2, "entry_view": "home", "start_flow": "home"}), encoding="utf-8")
    return resources


def test_starter_creates_v2_project_and_compilable_entrypoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = WorkspaceManager().create_starter(parent_path=str(tmp_path), name="My V2 Bot")
    root = Path(project["project_root"])
    assert (root / "resources" / "views" / "home.json").is_file()
    assert (root / "resources" / "templates" / "home.txt").is_file()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "core-v2.0.0" in pyproject
    assert "subdirectory=packages/tg-bot-core" in pyproject
    assert compileall.compile_dir(root / "src", quiet=1)
    monkeypatch.syspath_prepend(str(root / "src"))
    importlib.import_module("my_v2_bot.__main__")


def test_view_crud_preserves_unknown_fields_and_detects_external_change(tmp_path: Path) -> None:
    resources = v2_resources(tmp_path)
    path = resources / "views" / "home.json"
    path.write_text(json.dumps({"schema_version": 2, "id": "home", "text": {"inline": "Home"}, "keyboard": [], "custom": {"keep": True}}), encoding="utf-8")
    manager = WorkspaceManager()
    project = manager.open_project(str(tmp_path))
    current = manager.get_view(project["project_id"], "home")
    saved = manager.save_view(project["project_id"], "home", {**current["payload"], "text": {"inline": "Changed"}}, current["revision"])
    assert saved["payload"]["custom"] == {"keep": True}
    path.write_text(json.dumps({"schema_version": 2, "id": "home", "text": {"inline": "Outside"}, "keyboard": []}), encoding="utf-8")
    with pytest.raises(RevisionConflict):
        manager.save_view(project["project_id"], "home", saved["payload"], saved["revision"])


def test_v2_validation_preview_and_path_security(tmp_path: Path) -> None:
    resources = v2_resources(tmp_path)
    (resources / "views" / "home.json").write_text(json.dumps({"schema_version": 2, "id": "home", "text": {"template": "home.txt"}, "keyboard": [[{"text": "Start", "action": {"type": "flow.start", "target": "missing"}}]]}), encoding="utf-8")
    (resources / "templates" / "home.txt").write_text("Hello {{ user.name }}", encoding="utf-8")
    manager = WorkspaceManager()
    project = manager.open_project(str(tmp_path))
    preview = manager.preview(project["project_id"], manager.get_view(project["project_id"], "home")["payload"])
    issues = manager.validate(project["project_id"])
    assert preview["text"] == "Hello {{ user.name }}"
    assert any(issue["code"] == "flow_binding" for issue in issues)
    with pytest.raises(WorkspaceError):
        manager.save_template(project["project_id"], "../escape.txt", "no", None)


def test_v2_api_opens_and_creates_view(tmp_path: Path) -> None:
    v2_resources(tmp_path)
    client = TestClient(create_app())
    opened = client.post("/api/v1/projects/open", json={"root_path": str(tmp_path)}).json()
    created = client.post(f"/api/v1/projects/{opened['project_id']}/views", json={"view_id": "home", "payload": {"schema_version": 2, "id": "home", "text": {"inline": "Home"}, "keyboard": []}})
    assert created.status_code == 200
    assert client.get(f"/api/v1/projects/{opened['project_id']}/views/home").json()["payload"]["id"] == "home"
