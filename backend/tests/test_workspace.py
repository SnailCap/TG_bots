from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from tg_bot_core.project import ProjectLoader, validate_project

from app.workspace import ProjectService
from app.workspace.service import (
    ResourceConflict,
    ResourceInUse,
    RevisionConflict,
    WorkspaceError,
    WorkspaceNotFound,
)


def test_display_names_are_presentation_metadata_with_safe_generated_ids(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Display names")
    project_id = workspace["project_id"]

    created = service.create_view(project_id, None, {}, name="Первый экран")
    assert created["id"] == "pervyi_ekran"
    assert created["name"] == "Первый экран"
    assert created["payload"]["text"] == {"template": "views/pervyi_ekran.txt"}
    assert created["text_content"] == "Первый экран"
    assert created["name_is_default"] is False

    with pytest.raises(ResourceConflict, match="pervyi_ekran"):
        service.create_view(project_id, None, {}, name="Первый экран")

    default_view = service.create_view(project_id, None, {})
    assert default_view["id"] == "view_1"
    assert default_view["name"] == "View 1"
    assert default_view["name_is_default"] is True

    manifest = service.get_manifest(project_id)
    renamed = service.set_display_name(
        project_id,
        kind="views",
        key=default_view["id"],
        name="Welcome screen",
        revision=manifest["revision"],
    )
    assert renamed == {"name": "Welcome screen", "name_is_default": False}
    assert service.get_view(project_id, "view_1")["id"] == "view_1"
    assert service.get_view(project_id, "view_1")["name"] == "Welcome screen"


def test_slugify_display_name_transliterates_without_runtime_dependency() -> None:
    assert ProjectService.slugify_display_name("Первый экран", "view") == "pervyi_ekran"
    assert ProjectService.slugify_display_name("Crème brûlée", "view") == "creme_brulee"
    assert ProjectService.slugify_display_name("123", "view") == "view_123"


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
        "resources/variables.json",
        "resources/schedules/.gitkeep",
        "resources/views/home.json",
        "resources/flows/home.json",
        "resources/templates/views/home.txt",
        "src/my_v3_bot/__init__.py",
        "src/my_v3_bot/__main__.py",
        "src/my_v3_bot/_botstudio_variables.py",
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
    assert "119f2200566021ebf4d5bafa44c08805dcf236ed" in pyproject
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

    described_flow = next(
        item for item in service.describe(project_id)["flows"] if item["id"] == "details"
    )
    assert described_flow["states"] == ["show"]

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
    assert service.describe(project_id)["commands"]["items"] == [
        {"name": "help", "description": "Help"}
    ]

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


def test_view_text_storage_hydrates_and_canonicalizes_legacy_sources(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Preview Bot")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])

    home = service.get_view(project_id, "home")
    assert home["payload"]["text"] == {"template": "views/home.txt"}
    assert home["text_content"] == "Welcome to your bot!\n"
    saved = service.save_view(
        project_id,
        "home",
        home["payload"],
        home["revision"],
        text_content="Hello {{ user.first_name }}",
        text_revision=home["text_revision"],
    )
    preview = service.preview(
        project_id,
        {
            "text": saved["payload"]["text"],
            "keyboard": [[{"id": "noop", "text": "OK", "action": {"type": "noop"}}]],
        },
    )
    assert saved["text_content"] == "Hello {{ user.first_name }}"
    assert preview["text"] == saved["text_content"]
    assert preview["keyboard"][0][0]["id"] == "noop"

    (root / "resources" / "templates" / "views" / "home.txt").write_text(
        "Changed outside Studio", encoding="utf-8"
    )
    with pytest.raises(RevisionConflict):
        service.save_view(
            project_id,
            "home",
            saved["payload"],
            saved["revision"],
            text_content="Overwrite external change",
            text_revision=saved["text_revision"],
        )

    inline_path = root / "resources" / "views" / "legacy_inline.json"
    service.repository.atomic_write_json(
        inline_path,
        {
            "schema_version": 3,
            "id": "legacy_inline",
            "text": {"inline": "Legacy inline"},
            "keyboard": [],
        },
    )
    inline = service.get_view(project_id, "legacy_inline")
    assert inline["text_content"] == "Legacy inline"
    assert inline["text_revision"] is None
    canonical_inline = service.save_view(
        project_id,
        "legacy_inline",
        inline["payload"],
        inline["revision"],
        text_content="Updated inline",
        text_revision=None,
    )
    assert canonical_inline["payload"]["text"] == {
        "template": "views/legacy_inline.txt"
    }
    assert (root / "resources" / "templates" / "views" / "legacy_inline.txt").read_text(
        encoding="utf-8"
    ) == "Updated inline"

    legacy_template = root / "resources" / "templates" / "legacy.txt"
    legacy_template.write_text("Legacy template", encoding="utf-8")
    legacy_view_path = root / "resources" / "views" / "legacy_template.json"
    service.repository.atomic_write_json(
        legacy_view_path,
        {
            "schema_version": 3,
            "id": "legacy_template",
            "text": {"template": "legacy.txt"},
            "keyboard": [],
        },
    )
    legacy = service.get_view(project_id, "legacy_template")
    assert legacy["text_content"] == "Legacy template"
    canonical_legacy = service.save_view(
        project_id,
        "legacy_template",
        legacy["payload"],
        legacy["revision"],
        text_content="Canonical template",
        text_revision=legacy["text_revision"],
    )
    assert canonical_legacy["payload"]["text"] == {
        "template": "views/legacy_template.txt"
    }
    assert legacy_template.read_text(encoding="utf-8") == "Legacy template"

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
    root = Path(workspace["project_root"])
    assert not (root / "resources" / "templates" / "views" / "home.txt").exists()
    assert (root / "resources" / "templates" / "views" / "welcome.txt").is_file()
    assert renamed["payload"]["text"] == {"template": "views/welcome.txt"}


def test_legacy_view_rename_rollback_preserves_unowned_target_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Legacy Rename")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    resources = root / "resources"

    (resources / "templates" / "legacy.txt").write_text("Legacy", encoding="utf-8")
    target_template = resources / "templates" / "views" / "renamed.txt"
    target_template.write_text("Keep me", encoding="utf-8")
    service.repository.atomic_write_json(
        resources / "views" / "legacy.json",
        {
            "schema_version": 3,
            "id": "legacy",
            "text": {"template": "legacy.txt"},
            "keyboard": [],
        },
    )
    legacy = service.get_view(project_id, "legacy")
    original_load = service._load
    load_count = 0

    def fail_after_writes(workspace):
        nonlocal load_count
        load_count += 1
        if load_count == 2:
            raise WorkspaceError("simulated rename validation failure")
        return original_load(workspace)

    monkeypatch.setattr(service, "_load", fail_after_writes)
    with pytest.raises(WorkspaceError, match="simulated rename validation failure"):
        service.rename_view(project_id, "legacy", "renamed", legacy["revision"])

    assert (resources / "views" / "legacy.json").is_file()
    assert not (resources / "views" / "renamed.json").exists()
    assert target_template.read_text(encoding="utf-8") == "Keep me"


def test_renaming_flow_and_schedule_updates_resources(tmp_path: Path) -> None:
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

    schedule = service.create_schedule(
        project_id,
        "daily",
        {"handler": "tasks.daily", "trigger": {"type": "interval", "seconds": 60}, "payload": {}},
    )
    renamed_schedule = service.rename_schedule(project_id, "daily", "nightly", schedule["revision"])
    assert renamed_schedule["id"] == "nightly"
    assert [item["id"] for item in service.list_schedules(project_id)] == ["nightly"]


def test_delete_view_removes_only_its_owned_template(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Delete View Text")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])

    owned = service.create_view(
        project_id,
        "owned",
        {"text": {"inline": "Owned"}, "keyboard": []},
    )
    owned_template = root / "resources" / "templates" / "views" / "owned.txt"
    assert owned_template.is_file()
    service.delete_view(project_id, "owned", owned["revision"])
    assert not owned_template.exists()

    shared_template = root / "resources" / "templates" / "shared.txt"
    shared_template.write_text("Shared", encoding="utf-8")
    legacy_view_path = root / "resources" / "views" / "legacy.json"
    service.repository.atomic_write_json(
        legacy_view_path,
        {
            "schema_version": 3,
            "id": "legacy",
            "text": {"template": "shared.txt"},
            "keyboard": [],
        },
    )
    legacy = service.get_view(project_id, "legacy")
    service.delete_view(project_id, "legacy", legacy["revision"])
    assert shared_template.read_text(encoding="utf-8") == "Shared"


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
