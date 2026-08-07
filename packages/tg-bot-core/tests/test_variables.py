from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import time

import pytest

from tg_bot_core import (
    BotApp,
    BotConfig,
    CommandEvent,
    ResourceVariableContext,
    MissingVariableError,
    VariableAccessError,
    VariableCatalog,
    VariableRef,
    VariableTypeError,
    VariableValues,
    generate_variable_module,
)
from tg_bot_core.variables import render_variable_context
from tg_bot_core.project import ProjectLoader, validate_project
from tg_bot_core.store import SqliteStore
from tg_bot_core.events import Actor

from conftest import make_project, write_json
from conftest import FakeTransport, write_handler


def variable_payload(*variables: dict) -> dict:
    return {"schema_version": 3, "variables": list(variables)}


def order_total() -> dict:
    return {
        "id": "var_order_total",
        "owner": {"type": "flow", "id": "main"},
        "path": "order.total",
        "type": "number",
        "source": "custom",
        "writable": True,
        "persistence": "resource",
        "exposedToTemplates": True,
        "exampleValue": 120,
    }


def load_project(tmp_path: Path, *variables: dict):
    make_project(tmp_path)
    write_json(tmp_path / "resources" / "variables.json", variable_payload(*variables))
    return ProjectLoader().load(tmp_path)


def test_catalog_unifies_core_and_resource_scoped_custom_definitions(tmp_path: Path) -> None:
    view_label = {
        **order_total(),
        "id": "var_view_label",
        "owner": {"type": "view", "id": "home"},
        "path": "screen.label",
        "type": "string",
        "exampleValue": "Checkout",
    }
    project = load_project(tmp_path, order_total(), view_label)
    catalog = VariableCatalog(project)

    available = catalog.available(
        ResourceVariableContext(project.manifest.id, flow_id="main", instance_id="run-1")
    )

    assert {item.id for item in available} >= {
        "core.user.first_name",
        "var_order_total",
    }
    assert catalog.get("order.total").id == "var_order_total"
    assert "var_view_label" not in {item.id for item in available}
    view_available = catalog.available(
        ResourceVariableContext(project.manifest.id, view_id="home", instance_id="run-1")
    )
    assert "var_view_label" in {item.id for item in view_available}
    assert "var_order_total" not in {item.id for item in view_available}
    assert not [item for item in validate_project(project) if item.level == "error"]


def test_values_are_typed_read_only_aware_and_isolated_by_resource_instance(tmp_path: Path) -> None:
    project = load_project(tmp_path, order_total())
    catalog = VariableCatalog(project)
    first = VariableValues(
        catalog,
        ResourceVariableContext(project.manifest.id, flow_id="main", instance_id="run-1"),
        {},
        {"user.first_name": "Ada"},
    )
    reference = VariableRef[float]("var_order_total", "order.total")

    first.set(reference, 120)
    assert first.get(reference) == 120
    assert first.has(reference)
    with pytest.raises(VariableTypeError):
        first.set(reference, "120")  # type: ignore[arg-type]
    with pytest.raises(VariableAccessError, match="read-only"):
        first.set(VariableRef("core.user.first_name", "user.first_name"), "Grace")
    first.unset(reference)
    assert not first.has(reference)
    first.set(reference, 120)

    same_instance = VariableValues(
        catalog,
        ResourceVariableContext(project.manifest.id, flow_id="main", instance_id="run-1"),
        first._snapshot(),
    )
    other_instance = VariableValues(
        catalog,
        ResourceVariableContext(project.manifest.id, flow_id="main", instance_id="run-2"),
        first._snapshot(),
    )
    other_user = VariableValues(
        catalog,
        ResourceVariableContext(project.manifest.id, flow_id="main", instance_id="run-1"),
        {},
    )
    assert same_instance.get(reference) == 120
    assert other_instance.get(reference) is None
    assert other_user.get(reference) is None


def test_required_missing_values_fail_explicitly(tmp_path: Path) -> None:
    required = {**order_total(), "required": True}
    project = load_project(tmp_path, required)
    catalog = VariableCatalog(project)

    with pytest.raises(MissingVariableError, match="order.total"):
        render_variable_context(
            catalog,
            ResourceVariableContext(project.manifest.id, flow_id="main", instance_id="run-1"),
            {},
            {},
        )


def test_validation_rejects_conflicts_bad_defaults_and_unknown_owners(tmp_path: Path) -> None:
    conflicting = order_total()
    bad = {
        **order_total(),
        "id": "var_bad",
        "owner": {"type": "flow", "id": "missing"},
        "path": "order.total",
        "defaultValue": "not-a-number",
    }
    project = load_project(tmp_path, conflicting, bad)

    codes = {item.code for item in validate_project(project) if item.level == "error"}

    assert {"variable_path_conflict", "unknown_variable_owner", "variable_value_type_mismatch"} <= codes


def test_validation_reports_unknown_and_resource_unavailable_rich_references(
    tmp_path: Path,
) -> None:
    make_project(
        tmp_path,
        views=[{
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "Home", "document": "views/home.json"},
            "keyboard": [],
        }],
        handlers=[{
            "id": "private.prepare",
            "module": "fixture_bot.handlers.private_prepare",
            "symbol": "handle",
            "kind": "lifecycle",
        }],
    )
    handler_variable = {
        **order_total(),
        "id": "var_private_value",
        "owner": {"type": "handler", "id": "private.prepare"},
        "path": "private.value",
    }
    write_json(
        tmp_path / "resources" / "variables.json",
        variable_payload(handler_variable),
    )
    write_json(
        tmp_path / "resources" / "content" / "views" / "home.json",
        {
            "schemaVersion": 1,
            "id": "home",
            "content": [{
                "type": "paragraph",
                "content": [
                    {"type": "variable", "variableReference": {
                        "fieldId": "var_private_value",
                        "path": "private.value",
                    }},
                    {"type": "variable", "variableReference": {
                        "fieldId": "var_deleted",
                        "path": "deleted.value",
                    }},
                ],
            }],
            "metadata": {
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:00:00Z",
                "editorVersion": "1.0.0",
            },
        },
    )
    project = ProjectLoader().load(tmp_path)

    diagnostics = validate_project(project)

    assert any(item.code == "variable_unavailable" and item.level == "error" for item in diagnostics)
    assert any(item.code == "unknown_variable_reference" and item.level == "warning" for item in diagnostics)


def test_generated_module_is_a_projection_with_stable_refs(tmp_path: Path) -> None:
    project = load_project(tmp_path, order_total())

    source = generate_variable_module(project)

    assert "class Vars:" in source
    assert "class order:" in source
    assert 'VariableRef[float]("var_order_total", "order.total")' in source
    assert "resources/variables.json" in source


@pytest.mark.asyncio
async def test_store_expands_existing_sessions_without_losing_state(tmp_path: Path) -> None:
    path = tmp_path / "runtime.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE flow_sessions (
                bot_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                flow_id TEXT,
                state_id TEXT,
                view_id TEXT,
                variables_json TEXT NOT NULL,
                status TEXT NOT NULL,
                revision INTEGER NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (bot_id, user_id, chat_id)
            )"""
        )
        connection.execute(
            """INSERT INTO flow_sessions
            (bot_id, user_id, chat_id, username, first_name, last_name, flow_id,
             state_id, view_id, variables_json, status, revision, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "bot",
                1,
                10,
                None,
                "Ada",
                None,
                "main",
                "start",
                "home",
                json.dumps({"legacy": 1}),
                "active",
                1,
                time.time(),
            ),
        )
    store = SqliteStore(path)
    await store.initialize()
    actor = Actor(1, 10, first_name="Ada")
    loaded = await store.load_session("bot", actor)

    assert loaded.variables == {"legacy": 1}
    assert loaded.resource_variables == {}
    assert loaded.resource_instance_id is None


@pytest.mark.asyncio
async def test_runtime_ctx_vars_and_renderer_share_per_user_values(tmp_path: Path) -> None:
    make_project(
        tmp_path,
        views=[{
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "Total {{ order.total }} for {{ user.first_name }}"},
            "keyboard": [[{
                "id": "pay",
                "text": "Pay {{ order.total }}",
                "action": {"type": "noop"},
            }]],
        }],
        flows=[{
            "schema_version": 3,
            "id": "main",
            "initial_state": "start",
            "lifecycle": {
                "on_start": {
                    "handler": "order.prepare",
                    "outcomes": {"success": {"type": "noop"}},
                },
            },
            "states": {"start": {"view": "home"}},
        }],
        handlers=[{
            "id": "order.prepare",
            "module": "fixture_bot.handlers.order_prepare",
            "symbol": "handle",
            "kind": "lifecycle",
        }],
    )
    write_json(
        tmp_path / "resources" / "variables.json",
        variable_payload(order_total()),
    )
    write_handler(
        tmp_path,
        "fixture_bot.handlers.order_prepare",
        """from tg_bot_core import HandlerResult, LifecycleContext, VariableRef

TOTAL = VariableRef[float]("var_order_total", "order.total")

async def handle(ctx: LifecycleContext) -> HandlerResult:
    ctx.vars.set(TOTAL, 120 if ctx.user.id == 1 else 85)
    return HandlerResult.success()
""",
    )
    transport = FakeTransport()
    app = BotApp(
        config=BotConfig(
            project_root=tmp_path,
            token=None,
            database_path=tmp_path / "data" / "runtime.sqlite3",
        ),
        transport=transport,
    )
    await app.start()

    await transport.emit(CommandEvent(Actor(1, 10, first_name="Ada"), 1, "start"))
    await transport.emit(CommandEvent(Actor(2, 20, first_name="Grace"), 2, "start"))

    assert transport.messages[-2].text == "Total 120 for Ada"
    assert transport.messages[-2].keyboard[0][0].text == "Pay 120"
    assert transport.messages[-1].text == "Total 85 for Grace"
    assert transport.messages[-1].keyboard[0][0].text == "Pay 85"
    first = await app.store.load_session(app.project.manifest.id, Actor(1, 10))
    second = await app.store.load_session(app.project.manifest.id, Actor(2, 20))
    assert first.resource_instance_id != second.resource_instance_id
    assert first.resource_variables != second.resource_variables

    first_instance = first.resource_instance_id
    await transport.emit(CommandEvent(Actor(1, 10, first_name="Ada"), 3, "start"))
    restarted = await app.store.load_session(app.project.manifest.id, Actor(1, 10))
    assert restarted.resource_instance_id != first_instance
    assert len(restarted.resource_variables or {}) == 1
    await app.stop()


@pytest.mark.asyncio
async def test_required_runtime_value_uses_the_existing_flow_error_boundary(
    tmp_path: Path,
) -> None:
    make_project(
        tmp_path,
        views=[{
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "Total {{ order.total }}"},
            "keyboard": [],
        }],
    )
    write_json(
        tmp_path / "resources" / "variables.json",
        variable_payload({**order_total(), "required": True, "exampleValue": 120}),
    )
    transport = FakeTransport()
    app = BotApp(
        config=BotConfig(
            project_root=tmp_path,
            token=None,
            database_path=tmp_path / "data" / "runtime.sqlite3",
        ),
        transport=transport,
    )
    await app.start()

    await transport.emit(CommandEvent(Actor(1, 10, first_name="Ada"), 1, "start"))

    session = await app.store.load_session(app.project.manifest.id, Actor(1, 10))
    assert session.status == "failed"
    assert transport.messages[-1].text == "The bot could not complete that action."
    await app.stop()
