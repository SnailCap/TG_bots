from __future__ import annotations

from pathlib import Path

import pytest
from tg_bot_core.project import Diagnostic

from app.workspace import ProjectService
from app.workspace.service import (
    ResourceConflict,
    ResourceInUse,
    ResourceNotFound,
    RevisionConflict,
    WorkspaceError,
)


def add_button(service: ProjectService, project_id: str) -> dict:
    view = service.get_view(project_id, "home")
    payload = view["payload"]
    payload["keyboard"] = [
        [{"id": "run_custom", "text": "Run", "action": {"type": "noop"}}]
    ]
    return service.save_view(
        project_id,
        "home",
        payload,
        view["revision"],
        text_content=view["text_content"],
        text_revision=view["text_revision"],
    )


def test_scaffold_creates_one_file_binding_attachment_status_and_usages(
    tmp_path: Path,
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Handler Bot")
    project_id = workspace["project_id"]
    view = add_button(service, project_id)

    created = service.scaffold_handler(
        project_id,
        handler_id="checkout.submit",
        kind="button",
        outcomes=["invalid"],
        description="Submit checkout",
        registry_revision=service.list_handlers(project_id)["revision"],
        attachment={
            "type": "view_button",
            "view_id": "home",
            "button_id": "run_custom",
        },
        target_revision=view["revision"],
        routes={"invalid": {"type": "view.render", "target": "home"}},
    )

    assert created["file_created"] is True
    assert created["inspection"]["status"] == "ready"
    assert created["inspection"]["source"]["path"] == (
        "src/handler_bot/handlers/checkout/submit.py"
    )
    assert created["open_target"]["line"] == 4
    assert created["usages"] == [
        {
            "handler_id": "checkout.submit",
            "entity_type": "view_button",
            "entity_id": "run_custom",
            "field_path": "keyboard.0.0.action.handler",
            "source_path": "views/home.json",
        }
    ]
    action = service.get_view(project_id, "home")["payload"]["keyboard"][0][0]["action"]
    assert action["handler"] == "checkout.submit"
    assert action["outcomes"]["success"] == {"type": "noop"}
    assert not [issue for issue in service.validate(project_id) if issue["level"] == "error"]

    with pytest.raises(ResourceInUse):
        service.delete_handler(project_id, "checkout.submit", created["revision"])

    attached_view = service.get_view(project_id, "home")
    detached = service.detach_handler(
        project_id,
        "checkout.submit",
        attachment={
            "type": "view_button",
            "view_id": "home",
            "button_id": "run_custom",
        },
        target_revision=attached_view["revision"],
    )
    source = Path(created["open_target"]["file_path"])
    assert detached["inspection"]["status"] == "unused"
    assert source.is_file()
    service.delete_handler(project_id, "checkout.submit", detached["revision"])
    assert source.is_file()
    with pytest.raises(ResourceNotFound):
        service.get_handler(project_id, "checkout.submit")


def test_renaming_handler_updates_all_resource_references(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Rename Handler")
    project_id = workspace["project_id"]
    view = add_button(service, project_id)
    created = service.scaffold_handler(
        project_id,
        handler_id="checkout.submit",
        kind="button",
        outcomes=[],
        description=None,
        registry_revision=service.list_handlers(project_id)["revision"],
        attachment={"type": "view_button", "view_id": "home", "button_id": "run_custom"},
        target_revision=view["revision"],
        routes={"success": {"type": "noop"}},
    )

    renamed = service.rename_handler(
        project_id, "checkout.submit", "checkout.process", created["revision"]
    )

    assert renamed["id"] == "checkout.process"
    assert service.get_view(project_id, "home")["payload"]["keyboard"][0][0]["action"]["handler"] == "checkout.process"
    assert service.get_handler(project_id, "checkout.process")["inspection"]["status"] == "ready"
    assert not [issue for issue in service.validate(project_id) if issue["level"] == "error"]


def test_scaffold_never_overwrites_existing_handler_file(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Existing Handler")
    project_id = workspace["project_id"]
    source = (
        Path(workspace["project_root"])
        / "src"
        / "existing_handler"
        / "handlers"
        / "manual.py"
    )
    source.parent.mkdir(parents=True, exist_ok=True)
    original = (
        "from tg_bot_core import ButtonContext, HandlerResult\n\n"
        "# user-owned sentinel\n"
        "async def handle(ctx: ButtonContext) -> HandlerResult:\n"
        "    return HandlerResult.success()\n"
    )
    source.write_text(original, encoding="utf-8")

    created = service.scaffold_handler(
        project_id,
        handler_id="manual",
        kind="button",
        outcomes=[],
        description=None,
        registry_revision=service.list_handlers(project_id)["revision"],
    )

    assert created["file_created"] is False
    assert source.read_text(encoding="utf-8") == original
    assert created["inspection"]["status"] == "unused"


def test_repair_restores_only_missing_canonical_source(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Repair Handler")
    project_id = workspace["project_id"]
    view = add_button(service, project_id)
    created = service.scaffold_handler(
        project_id,
        handler_id="checkout.repair",
        kind="button",
        outcomes=[],
        description="Repair checkout",
        registry_revision=service.list_handlers(project_id)["revision"],
        attachment={
            "type": "view_button",
            "view_id": "home",
            "button_id": "run_custom",
        },
        target_revision=view["revision"],
    )
    root = Path(workspace["project_root"])
    source = Path(created["open_target"]["file_path"])
    registry_path = root / "resources" / "handlers.json"
    view_path = root / "resources" / "views" / "home.json"
    registry_before = registry_path.read_bytes()
    view_before = view_path.read_bytes()
    source.unlink()

    assert service.get_handler(project_id, "checkout.repair")["inspection"]["status"] == (
        "missing_file"
    )
    with pytest.raises(RevisionConflict):
        service.repair_handler(
            project_id,
            "checkout.repair",
            registry_revision="stale-revision",
        )
    assert not source.exists()

    repaired = service.repair_handler(
        project_id,
        "checkout.repair",
        registry_revision=created["revision"],
    )

    assert repaired["file_created"] is True
    assert repaired["inspection"]["status"] == "ready"
    assert Path(repaired["open_target"]["file_path"]) == source
    assert "async def handle(ctx: ButtonContext) -> HandlerResult:" in source.read_text(
        encoding="utf-8"
    )
    assert registry_path.read_bytes() == registry_before
    assert view_path.read_bytes() == view_before

    repaired_source = source.read_bytes()
    with pytest.raises(ResourceConflict):
        service.repair_handler(
            project_id,
            "checkout.repair",
            registry_revision=created["revision"],
        )
    assert source.read_bytes() == repaired_source


def test_repair_rolls_back_generated_files_when_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Repair Rollback")
    project_id = workspace["project_id"]
    created = service.scaffold_handler(
        project_id,
        handler_id="nested.rollback",
        kind="task",
        outcomes=[],
        description=None,
        registry_revision=service.list_handlers(project_id)["revision"],
    )
    source = Path(created["open_target"]["file_path"])
    initializer = source.parent / "__init__.py"
    source.unlink()
    initializer.unlink()
    monkeypatch.setattr(
        "app.workspace.service.validate_project",
        lambda *_args, **_kwargs: [
            Diagnostic("error", "simulated", "simulated validation failure")
        ],
    )

    with pytest.raises(WorkspaceError, match="simulated validation failure"):
        service.repair_handler(
            project_id,
            "nested.rollback",
            registry_revision=created["revision"],
        )

    assert not source.exists()
    assert not initializer.exists()


def test_scaffold_rolls_back_binding_reference_and_new_file_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Atomic Handler")
    project_id = workspace["project_id"]
    view = add_button(service, project_id)
    original_write = service.repository.atomic_write_json
    writes = 0

    def fail_second_write(path: Path, payload: dict) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated attachment write failure")
        original_write(path, payload)

    monkeypatch.setattr(service.repository, "atomic_write_json", fail_second_write)
    with pytest.raises(OSError, match="simulated"):
        service.scaffold_handler(
            project_id,
            handler_id="atomic.run",
            kind="button",
            outcomes=[],
            description=None,
            registry_revision=service.list_handlers(project_id)["revision"],
            attachment={
                "type": "view_button",
                "view_id": "home",
                "button_id": "run_custom",
            },
            target_revision=view["revision"],
        )

    assert service.list_handlers(project_id)["handlers"] == []
    assert service.get_view(project_id, "home")["payload"]["keyboard"][0][0]["action"] == {
        "type": "noop"
    }
    source = (
        Path(workspace["project_root"])
        / "src"
        / "atomic_handler"
        / "handlers"
        / "atomic"
        / "run.py"
    )
    assert not source.exists()


def test_handler_ast_statuses_and_path_rejection(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Inspect Handler")
    project_id = workspace["project_id"]
    created = service.scaffold_handler(
        project_id,
        handler_id="inspect",
        kind="message",
        outcomes=[],
        description=None,
        registry_revision=service.list_handlers(project_id)["revision"],
    )
    source = Path(created["open_target"]["file_path"])
    source.write_text("def handle(ctx):\n    return None\n", encoding="utf-8")
    assert service.get_handler(project_id, "inspect")["inspection"]["status"] == (
        "invalid_signature"
    )

    with pytest.raises(WorkspaceError):
        service.scaffold_handler(
            project_id,
            handler_id="../escape",
            kind="button",
            outcomes=[],
            description=None,
            registry_revision=service.list_handlers(project_id)["revision"],
        )


def test_scaffold_can_attach_global_message_fallback(tmp_path: Path) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Fallback Handler")
    project_id = workspace["project_id"]
    commands = service.get_commands(project_id)

    created = service.scaffold_handler(
        project_id,
        handler_id="fallback.message",
        kind="message",
        outcomes=[],
        description=None,
        registry_revision=service.list_handlers(project_id)["revision"],
        attachment={"type": "global_message_fallback"},
        target_revision=commands["revision"],
    )

    assert created["inspection"]["status"] == "ready"
    action = service.get_commands(project_id)["payload"]["message_fallback"]
    assert action == {
        "type": "handler.invoke",
        "handler": "fallback.message",
        "outcomes": {"success": {"type": "noop"}},
    }
    assert not [issue for issue in service.validate(project_id) if issue["level"] == "error"]
