from __future__ import annotations

from pathlib import Path

import pytest

from app.workspace import ProjectService
from app.workspace.service import ResourceInUse, WorkspaceError


def variable_definition(*, path: str = "order.total") -> dict:
    return {
        "id": "var_order_total",
        "owner": {"type": "flow", "id": "home"},
        "path": path,
        "type": "number",
        "source": "custom",
        "required": True,
        "writable": True,
        "exampleValue": 120,
        "persistence": "resource",
        "exposedToTemplates": True,
    }


def variable_document(path: str = "order.total") -> dict:
    return {
        "schemaVersion": 1,
        "id": "home",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Total: "},
                    {
                        "type": "variable",
                        "variableReference": {
                            "fieldId": "var_order_total",
                            "path": path,
                            "source": f"{{{{ {path} }}}}",
                        },
                    },
                ],
            }
        ],
        "metadata": {
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "editorVersion": "1.0.0",
        },
    }


def test_catalog_crud_generates_refs_and_preserves_stable_rich_references(
    tmp_path: Path,
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Variable Bot")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])

    initial = service.get_variables(project_id, resource_type="flow", resource_id="home")
    assert {item["id"] for item in initial["definitions"]} == {
        "core.user.first_name",
        "core.user.last_name",
        "core.user.username",
        "core.user.telegram_id",
        "core.user.language_code",
    }

    saved = service.save_variables(
        project_id,
        {"schema_version": 3, "variables": [variable_definition()]},
        initial["revision"],
    )
    assert any(item["id"] == "var_order_total" for item in saved["definitions"])
    generated = root / "src" / "variable_bot" / "_botstudio_variables.py"
    assert 'VariableRef[float]("var_order_total", "order.total")' in generated.read_text(
        encoding="utf-8"
    )

    renamed_payload = saved["payload"]
    renamed_payload["variables"][0]["path"] = "order.final_price"
    renamed = service.save_variables(project_id, renamed_payload, saved["revision"])
    definition = renamed["payload"]["variables"][0]
    assert definition["id"] == "var_order_total"
    assert definition["legacyPaths"] == ["order.total"]
    assert "final_price = VariableRef[float]" in generated.read_text(encoding="utf-8")

    compiled = service.compile_content(
        project_id,
        variable_document(),
        variables={"order": {"final_price": 185}},
    )
    assert compiled["messages"][0]["text"] == "Total: 185"

    template = root / "resources" / "templates" / "views" / "home.txt"
    template.write_text("Total: {{ order.total | round }}", encoding="utf-8")
    with pytest.raises(ResourceInUse, match="referenced"):
        service.save_variables(
            project_id,
            {"schema_version": 3, "variables": []},
            renamed["revision"],
        )


def test_catalog_save_is_revisioned_validated_and_does_not_overwrite_user_code(
    tmp_path: Path,
) -> None:
    service = ProjectService()
    workspace = service.create_starter(parent_path=str(tmp_path), name="Protected Vars")
    project_id = workspace["project_id"]
    root = Path(workspace["project_root"])
    current = service.get_variables(project_id)

    invalid = variable_definition()
    invalid["owner"] = {"type": "flow", "id": "missing"}
    with pytest.raises(WorkspaceError, match="unknown flow"):
        service.save_variables(
            project_id,
            {"schema_version": 3, "variables": [invalid]},
            current["revision"],
        )
    assert service.get_variables(project_id)["payload"]["variables"] == []

    generated = root / "src" / "protected_vars" / "_botstudio_variables.py"
    saved = service.save_variables(
        project_id,
        {"schema_version": 3, "variables": [variable_definition()]},
        current["revision"],
    )
    assert "var_order_total" in generated.read_text(encoding="utf-8")
    removed = service.save_variables(
        project_id,
        {"schema_version": 3, "variables": []},
        saved["revision"],
    )
    assert "var_order_total" not in generated.read_text(encoding="utf-8")

    generated.write_text("# user-owned module\n", encoding="utf-8")
    with pytest.raises(WorkspaceError, match="non-generated"):
        service.save_variables(
            project_id,
            {"schema_version": 3, "variables": [variable_definition()]},
            removed["revision"],
        )
    assert generated.read_text(encoding="utf-8") == "# user-owned module\n"
    assert service.get_variables(project_id)["payload"]["variables"] == []
