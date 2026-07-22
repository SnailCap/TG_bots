from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from tg_bot_core.project import ProjectLoader, validate_project

from app.workspace import ProjectService
from app.workspace.service import (
    ResourceInUse,
    RevisionConflict,
    WorkspaceError,
    WorkspaceNotFound,
)


def test_starter_is_atomic_autonomous_v3_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="My V3 Bot")
    root = Path(workspace["project_root"])

    expected = (
        "resources/bot.json",
        "resources/handlers.json",
        "resources/commands.json",
        "resources/schedules/.gitkeep",
        "resources/views/home.json",
        "resources/flows/home.json",
        "resources/templates/home.txt",
        "src/my_v3_bot/__init__.py",
        "src/my_v3_bot/__main__.py",
        "src/my_v3_bot/handlers/__init__.py",
        "src/my_v3_bot/services/__init__.py",
        "tests/test_project.py",
        "README.md",
        "Dockerfile",
        "pyproject.toml",
    )
    assert all((root / relative).is_file() for relative in expected)
    assert (root / "resources" / "schedules").is_dir()
    assert (root / "data").is_dir()

    gitignore = set((root / ".gitignore").read_text(encoding="utf-8").splitlines())
    assert {
        "data/*.sqlite3-wal",
        "data/*.sqlite3-shm",
        "*.egg-info/",
        "build/",
        "dist/",
    } <= gitignore
    assert "STOPSIGNAL SIGTERM" in (root / "Dockerfile").read_text(encoding="utf-8")

    project = ProjectLoader().load(root)
    assert project.manifest.schema_version == 3
    assert project.manifest.package == "my_v3_bot"
    assert not [item for item in validate_project(project, inspect_code=True) if item.level == "error"]

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "core-v3.0.0" in pyproject
    assert "subdirectory=packages/tg-bot-core" in pyproject
    generated_python = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "src").rglob("*.py")
    )
    assert "app.workspace" not in generated_python
    assert "backend" not in generated_python
    assert "BotModule" not in generated_python
    assert "logging.basicConfig" in generated_python
    assert "stream=sys.stdout" in generated_python
    assert "Bot process stopped because of an unhandled error" in generated_python

    monkeypatch.syspath_prepend(str(root / "src"))
    entrypoint = importlib.import_module("my_v3_bot.__main__")
    monkeypatch.chdir(root)
    assert entrypoint.main(["--validate"]) == 0

    reopened = service.open_project(str(root))
    assert reopened["project_id"] == workspace["project_id"]


def test_failed_starter_does_not_leave_final_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()

    def fail_load(root: Path):
        raise ValueError("simulated validation failure")

    monkeypatch.setattr(service.starter._loader, "load", fail_load)
    with pytest.raises(WorkspaceError, match="simulated validation failure"):
        service.create_starter(parent_path=str(tmp_path), name="Broken Bot")

    assert not (tmp_path / "broken-bot").exists()
    assert not list(tmp_path.glob(".broken-bot.studio-*"))


def test_open_failure_removes_published_starter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()

    def fail_open(_root: Path):
        raise WorkspaceError("simulated open failure")

    monkeypatch.setattr(service.repository, "open", fail_open)
    with pytest.raises(WorkspaceError, match="simulated open failure"):
        service.create_starter(parent_path=str(tmp_path), name="Open Failure")

    assert not (tmp_path / "open-failure").exists()


def test_describe_failure_removes_starter_and_forgets_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()
    opened_id: str | None = None
    original_open = service.repository.open

    def capture_open(root: Path):
        nonlocal opened_id
        workspace = original_open(root)
        opened_id = workspace.id
        return workspace

    def fail_describe(_project_id: str):
        raise WorkspaceError("simulated describe failure")

    monkeypatch.setattr(service.repository, "open", capture_open)
    monkeypatch.setattr(service, "describe", fail_describe)
    with pytest.raises(WorkspaceError, match="simulated describe failure"):
        service.create_starter(parent_path=str(tmp_path), name="Describe Failure")

    assert not (tmp_path / "describe-failure").exists()
    assert opened_id is not None
    with pytest.raises(WorkspaceNotFound):
        service.repository.workspace(opened_id)


def test_v3_resource_crud_revisions_commands_and_reference_safe_delete(
    tmp_path: Path,
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="CRUD Bot")
    project_id = workspace["project_id"]

    view = service.create_view(
        project_id,
        "details",
        {"text": {"inline": "Details"}, "keyboard": []},
    )
    assert view["payload"]["schema_version"] == 3
    assert view["payload"]["id"] == "details"

    flow = service.create_flow(
        project_id,
        "details",
        {
            "initial_state": "show",
            "lifecycle": {},
            "states": {"show": {"view": "details", "events": {}}},
        },
    )
    changed = service.save_flow(
        project_id,
        "details",
        {
            **flow["payload"],
            "states": {"show": {"view": "details", "events": {}}},
            "editor_metadata": {"changed": True},
        },
        flow["revision"],
    )
    assert changed["revision"] != flow["revision"]
    with pytest.raises(RevisionConflict):
        service.save_flow(project_id, "details", changed["payload"], flow["revision"])

    with pytest.raises(ResourceInUse):
        service.delete_view(project_id, "details", view["revision"])

    commands = service.get_commands(project_id)
    saved_commands = service.save_commands(
        project_id,
        {
            "commands": [
                {
                    "name": "help",
                    "description": "Help",
                    "action": {"type": "view.render", "target": "home"},
                }
            ]
        },
        commands["revision"],
    )
    assert saved_commands["payload"]["commands"][0]["name"] == "help"

    schedule = service.create_schedule(
        project_id,
        "digest",
        {
            "handler": "tasks.digest",
            "trigger": {"type": "interval", "seconds": 60},
            "payload": {},
        },
    )
    assert service.get_schedule(project_id, "digest")["revision"] == schedule["revision"]
    service.delete_schedule(project_id, "digest", schedule["revision"])
    assert service.list_schedules(project_id) == []


def test_preview_templates_manifest_and_path_containment(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Preview Bot")
    project_id = workspace["project_id"]

    template = service.get_template(project_id, "home.txt")
    saved = service.save_template(
        project_id,
        "home.txt",
        "Hello {{ user.first_name }}",
        template["revision"],
    )
    preview = service.preview(
        project_id,
        {
            "text": {"template": "home.txt"},
            "keyboard": [[{"id": "noop", "text": "OK", "action": {"type": "noop"}}]],
        },
    )
    assert saved["content"] == "Hello {{ user.first_name }}"
    assert preview["text"] == saved["content"]
    assert preview["keyboard"][0][0]["id"] == "noop"

    with pytest.raises(ResourceInUse):
        service.delete_template(project_id, "home.txt", saved["revision"])

    unused = service.save_template(project_id, "unused.txt", "", None)
    service.delete_template(project_id, "unused.txt", unused["revision"])
    assert {item["path"] for item in service.describe(project_id)["templates"]} == {"home.txt"}

    with pytest.raises(WorkspaceError):
        service.save_template(project_id, "../escape.txt", "no", None)

    manifest = service.get_manifest(project_id)
    invalid = json.loads(json.dumps(manifest["payload"]))
    invalid["package"] = "other_package"
    with pytest.raises(WorkspaceError, match="Changing"):
        service.save_manifest(project_id, invalid, manifest["revision"])


def test_renaming_a_view_updates_project_references(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Rename Bot")
    project_id = workspace["project_id"]
    home = service.get_view(project_id, "home")

    renamed = service.rename_view(project_id, "home", "welcome", home["revision"])

    assert renamed["id"] == "welcome"
    assert service.get_manifest(project_id)["payload"]["entry_view"] == "welcome"
    assert service.get_flow(project_id, "home")["payload"]["states"]["home"]["view"] == "welcome"
    assert [item["id"] for item in service.describe(project_id)["views"]] == ["welcome"]


def test_renaming_flow_template_and_schedule_updates_resources(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Rename Resources")
    project_id = workspace["project_id"]

    commands = service.get_commands(project_id)
    service.save_commands(
        project_id,
        {"commands": [{"name": "begin", "action": {"type": "flow.start", "target": "home"}}]},
        commands["revision"],
    )
    flow = service.get_flow(project_id, "home")
    renamed_flow = service.rename_flow(project_id, "home", "welcome", flow["revision"])
    assert renamed_flow["id"] == "welcome"
    assert service.get_manifest(project_id)["payload"]["start"]["flow"] == "welcome"
    assert service.get_commands(project_id)["payload"]["commands"][0]["action"]["target"] == "welcome"

    template = service.get_template(project_id, "home.txt")
    renamed_template = service.rename_template(
        project_id, "home.txt", "welcome.txt", template["revision"]
    )
    assert renamed_template["path"] == "welcome.txt"
    assert service.get_view(project_id, "home")["payload"]["text"]["template"] == "welcome.txt"

    schedule = service.create_schedule(
        project_id,
        "daily",
        {"handler": "tasks.daily", "trigger": {"type": "interval", "seconds": 60}, "payload": {}},
    )
    renamed_schedule = service.rename_schedule(project_id, "daily", "nightly", schedule["revision"])
    assert renamed_schedule["id"] == "nightly"
    assert [item["id"] for item in service.list_schedules(project_id)] == ["nightly"]


def test_validation_uses_the_shared_project_load_code(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Broken JSON")
    project_id = workspace["project_id"]
    manifest = Path(workspace["project_root"]) / "resources" / "bot.json"
    manifest.write_text("{", encoding="utf-8")

    issues = service.validate(project_id)

    assert len(issues) == 1
    assert issues[0]["level"] == "error"
    assert issues[0]["code"] == "project_load"
    assert "Cannot read JSON resource" in issues[0]["message"]
