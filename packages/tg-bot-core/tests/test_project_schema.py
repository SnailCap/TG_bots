from __future__ import annotations

import json
from pathlib import Path

import pytest

from tg_bot_core.catalog import CallbackCodec, CatalogError, ProjectCatalog
from tg_bot_core.project import (
    ProjectLoadError,
    ProjectLoader,
    load_and_validate_project,
    validate_project,
)

from conftest import make_project, write_handler, write_json


def test_callback_codec_uses_short_v3_action_ids_and_enforces_telegram_limit() -> None:
    codec = CallbackCodec()
    maximum_id = "a" * 59

    encoded = codec.encode(maximum_id)

    assert encoded == f"v3:a:{maximum_id}"
    assert len(encoded.encode("utf-8")) == 64
    assert codec.decode(encoded) == maximum_id
    with pytest.raises(CatalogError, match="64-byte"):
        codec.encode("a" * 60)
    with pytest.raises(CatalogError, match="not a schema v3"):
        codec.decode("v2:a:old")
    with pytest.raises(CatalogError, match="empty"):
        codec.decode("v3:a:")


def test_loader_builds_complete_typed_project_and_validation_passes(tmp_path: Path) -> None:
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"template": "home.txt"},
            "keyboard": [[{"id": "begin", "text": "Begin", "action": {"type": "flow.start", "target": "main"}}]],
        },
        {"schema_version": 3, "id": "ask", "text": {"inline": "Your name?"}, "keyboard": []},
        {"schema_version": 3, "id": "done", "text": {"inline": "Done {{ name }}"}, "keyboard": []},
    ]
    handlers = [
        {
            "id": "profile.save",
            "module": "fixture_bot.handlers.profile_save",
            "symbol": "handle",
            "kind": "message",
            "outcomes": ["invalid"],
        },
        {
            "id": "digest.send",
            "module": "fixture_bot.handlers.digest_send",
            "symbol": "handle",
            "kind": "task",
        },
    ]
    flows = [
        {
            "schema_version": 3,
            "id": "main",
            "initial_state": "ask",
            "states": {
                "ask": {
                    "view": "ask",
                    "on_message": {
                        "handler": "profile.save",
                        "outcomes": {
                            "success": {"type": "flow.finish", "view": "done"},
                            "invalid": {"type": "view.render", "target": "ask"},
                        },
                    },
                }
            },
        }
    ]
    schedules = [
        {
            "schema_version": 3,
            "id": "daily-digest",
            "handler": "digest.send",
            "trigger": {"type": "interval", "seconds": 86400},
            "payload": {"chat_id": 42},
        }
    ]
    make_project(
        tmp_path,
        views=views,
        flows=flows,
        handlers=handlers,
        commands={
            "commands": [
                {"name": "help", "description": "Show help", "action": {"type": "view.render", "target": "home"}}
            ]
        },
        schedules=schedules,
        templates={"home.txt": "Hello {{ user.first_name }}"},
    )
    write_handler(
        tmp_path,
        "fixture_bot.handlers.profile_save",
        "from tg_bot_core import HandlerResult, MessageContext\n\nasync def handle(ctx: MessageContext) -> HandlerResult:\n    return HandlerResult.success()\n",
    )
    write_handler(
        tmp_path,
        "fixture_bot.handlers.digest_send",
        "from tg_bot_core import HandlerResult, TaskContext\n\nasync def handle(ctx: TaskContext) -> HandlerResult:\n    return HandlerResult.success()\n",
    )

    project = ProjectLoader().load(tmp_path)

    assert project.manifest.schema_version == 3
    assert project.manifest.package == "fixture_bot"
    assert project.views["home"].text.template == "home.txt"
    assert project.flows["main"].states["ask"].on_message is not None
    assert project.handlers["profile.save"].outcomes == ("invalid",)
    assert project.commands.commands[0].name == "help"
    assert project.schedules["daily-digest"].trigger.seconds == 86400
    assert project.actions["begin"].type == "flow.start"
    assert not [item for item in validate_project(project, inspect_code=True) if item.level == "error"]


def test_loader_prefers_nested_resources_for_a_project_named_resources(tmp_path: Path) -> None:
    project_root = tmp_path / "resources"
    make_project(project_root)

    project = ProjectLoader().load(project_root)

    assert project.root == project_root.resolve()
    assert project.resources == (project_root / "resources").resolve()


def test_manifest_display_names_are_optional_presentation_metadata(tmp_path: Path) -> None:
    make_project(tmp_path)

    legacy = ProjectLoader().load(tmp_path)
    assert legacy.manifest.display_names == {}

    manifest_path = tmp_path / "resources" / "bot.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["display_names"] = {"views": {"home": "Главный экран"}}
    write_json(manifest_path, manifest)

    project = ProjectLoader().load(tmp_path)
    assert project.manifest.display_names == {"views": {"home": "Главный экран"}}
    assert not [item for item in validate_project(project) if item.level == "error"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda root: write_json(root / "resources" / "bot.json", {"schema_version": 2}), "schema_version must be 3"),
        (
            lambda root: write_json(
                root / "resources" / "views" / "home.json",
                {
                    "schema_version": 3,
                    "id": "home",
                    "text": {"inline": "Home"},
                    "keyboard": [[{"id": "bad", "text": "Bad", "action": {"type": "noop", "target": "extra"}}]],
                },
            ),
            "unsupported fields for noop",
        ),
        (
            lambda root: write_json(
                root / "resources" / "views" / "home.json",
                {
                    "schema_version": 3,
                    "id": "home",
                    "text": {"inline": "Home"},
                    "keyboard": [[{"id": "bad", "text": "Bad", "action": {"type": "view.render", "target": "home", "delivery": "replace"}}]],
                },
            ),
            "delivery must be 'edit' or 'send'",
        ),
    ],
)
def test_loader_rejects_wrong_version_and_ambiguous_actions(tmp_path: Path, mutate, match: str) -> None:
    make_project(tmp_path)
    mutate(tmp_path)

    with pytest.raises(ProjectLoadError, match=match):
        ProjectLoader().load(tmp_path)


@pytest.mark.parametrize("seconds", [True, float("nan"), float("inf")])
def test_loader_rejects_non_finite_or_boolean_schedule_numbers(
    tmp_path: Path,
    seconds: object,
) -> None:
    make_project(
        tmp_path,
        schedules=[
            {
                "schema_version": 3,
                "id": "bad",
                "handler": "task.run",
                "trigger": {"type": "interval", "seconds": seconds},
                "payload": {},
            }
        ],
    )

    with pytest.raises(ProjectLoadError, match="finite|non-finite"):
        ProjectLoader().load(tmp_path)


def test_negative_task_delay_is_a_validation_error(tmp_path: Path) -> None:
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "Home"},
            "keyboard": [[
                {
                    "id": "queue",
                    "text": "Queue",
                    "action": {
                        "type": "task.enqueue",
                        "target": "task.run",
                        "delay_seconds": -1,
                    },
                }
            ]],
        }
    ]
    handlers = [
        {
            "id": "task.run",
            "module": "fixture_bot.handlers.task_run",
            "symbol": "handle",
            "kind": "task",
        }
    ]
    make_project(tmp_path, views=views, handlers=handlers)

    codes = {item.code for item in validate_project(ProjectLoader().load(tmp_path))}

    assert "invalid_action_delay" in codes


def test_load_failure_uses_shared_project_load_diagnostic(tmp_path: Path) -> None:
    project, diagnostics = load_and_validate_project(tmp_path)

    assert project is None
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "project_load"


def test_templates_are_validated_once_at_their_own_source_path(tmp_path: Path) -> None:
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"template": "broken.txt"},
            "keyboard": [],
        },
        {
            "schema_version": 3,
            "id": "other",
            "text": {"template": "broken.txt"},
            "keyboard": [],
        },
    ]
    make_project(
        tmp_path,
        views=views,
        templates={"broken.txt": "{{ broken", "unused.txt": "  "},
    )

    diagnostics = validate_project(ProjectLoader().load(tmp_path))
    syntax = [item for item in diagnostics if item.code == "jinja_syntax"]

    assert len(syntax) == 1
    assert syntax[0].source_path == "templates/broken.txt"
    assert any(
        item.code == "template_empty" and item.source_path == "templates/unused.txt"
        for item in diagnostics
    )


def test_empty_inline_and_empty_rendered_output_are_rejected(tmp_path: Path) -> None:
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "   "},
            "keyboard": [],
        },
        {
            "schema_version": 3,
            "id": "dynamic",
            "text": {"inline": "{{ value | default('') }}"},
            "keyboard": [],
        },
        {
            "schema_version": 3,
            "id": "long",
            "text": {"inline": "{{ value }}"},
            "keyboard": [],
        },
    ]
    make_project(tmp_path, views=views)
    project = ProjectLoader().load(tmp_path)

    assert any(item.code == "view_text_empty" for item in validate_project(project))
    catalog = ProjectCatalog(project)
    with pytest.raises(CatalogError, match="empty Telegram message"):
        catalog.render("dynamic", {})
    with pytest.raises(CatalogError, match="at most 4096"):
        catalog.render("long", {"value": "x" * 4097})


def test_cross_resource_validation_reports_stable_diagnostic_codes(tmp_path: Path) -> None:
    long_action_id = "a" * 60
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"template": "missing.txt"},
            "keyboard": [[
                {
                    "id": long_action_id,
                    "text": "Run",
                    "action": {
                        "type": "handler.invoke",
                        "handler": "wrong.kind",
                        "outcomes": {},
                    },
                }
            ]],
        },
        {
            "schema_version": 3,
            "id": "other",
            "text": {"inline": "{{ broken"},
            "keyboard": [[{"id": long_action_id, "text": "Again", "action": {"type": "noop"}}]],
        },
    ]
    flows = [
        {
            "schema_version": 3,
            "id": "main",
            "initial_state": "start",
            "states": {
                "start": {
                    "view": "unknown",
                    "on_message": {"handler": "missing.handler", "outcomes": {"success": {"type": "noop"}}},
                },
                "orphan": {"view": "home"},
            },
        }
    ]
    handlers = [
        {
            "id": "wrong.kind",
            "module": "outside.handlers.bad",
            "symbol": "handle",
            "kind": "message",
        },
        {
            "id": "unused.task",
            "module": "fixture_bot.handlers.unused",
            "symbol": "handle",
            "kind": "task",
        },
    ]
    schedules = [
        {
            "schema_version": 3,
            "id": "bad-schedule",
            "handler": "unknown.task",
            "trigger": {"type": "cron"},
            "payload": {},
        }
    ]
    make_project(
        tmp_path,
        bot={"entry_view": "missing-entry"},
        views=views,
        flows=flows,
        handlers=handlers,
        commands={
            "commands": [
                {"name": "start", "action": {"type": "noop"}},
                {"name": "HELP", "action": {"type": "noop"}},
                {"name": "help", "action": {"type": "noop"}},
            ]
        },
        schedules=schedules,
    )

    codes = {item.code for item in validate_project(ProjectLoader().load(tmp_path))}

    assert {
        "missing_entry_view",
        "duplicate_action_id",
        "callback_encoding_invalid",
        "template_missing",
        "jinja_syntax",
        "handler_kind_mismatch",
        "outcome_route_missing",
        "handler_binding_missing",
        "missing_state_view",
        "unreachable_state",
        "command_collision",
        "invalid_command",
        "unsupported_schedule_trigger",
        "invalid_schedule_trigger",
        "invalid_handler_module",
        "unused_handler",
    } <= codes


def test_flow_event_action_requires_a_declared_event_and_button_context(tmp_path: Path) -> None:
    views = [
        {
            "schema_version": 3,
            "id": "home",
            "text": {"inline": "Home"},
            "keyboard": [[
                {
                    "id": "emit-missing",
                    "text": "Run",
                    "action": {"type": "flow.event", "target": "missing"},
                }
            ]],
        }
    ]
    flows = [
        {
            "schema_version": 3,
            "id": "main",
            "initial_state": "start",
            "states": {
                "start": {
                    "view": "home",
                    "events": {
                        "known": {
                            "handler": "event.handle",
                            "outcomes": {"success": {"type": "noop"}},
                        }
                    },
                }
            },
        }
    ]
    handlers = [
        {
            "id": "event.handle",
            "module": "fixture_bot.handlers.event_handle",
            "symbol": "handle",
            "kind": "button",
        }
    ]
    commands = {
        "commands": [
            {
                "name": "emit",
                "action": {"type": "flow.event", "target": "known"},
            }
        ]
    }
    make_project(
        tmp_path,
        views=views,
        flows=flows,
        handlers=handlers,
        commands=commands,
    )

    diagnostics = validate_project(ProjectLoader().load(tmp_path))
    unknown = [item for item in diagnostics if item.code == "unknown_event_reference"]

    assert len(unknown) == 1
    assert unknown[0].source_path == "views/home.json"
    assert unknown[0].entity_id == "emit-missing"
    assert unknown[0].field_path == "keyboard.0.0.action.target"
    assert "action_context_invalid" in {item.code for item in diagnostics}


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("async def other(ctx):\n    return None\n", "handler_symbol_missing"),
        ("def handle(ctx):\n    return None\n", "handler_signature_invalid"),
        ("async def handle(first, second):\n    return None\n", "handler_signature_invalid"),
        ("async def handle(ctx: CommandContext):\n    return None\n", "handler_signature_invalid"),
        (
            "from tg_bot_core import HandlerResult, MessageContext\n\n"
            "async def handle(ctx: MessageContext, *, audit: bool = False) -> HandlerResult:\n"
            "    return HandlerResult.success()\n",
            "handler_signature_invalid",
        ),
    ],
)
def test_handler_source_inspection_reports_missing_or_invalid_symbol(
    tmp_path: Path, source: str, expected_code: str
) -> None:
    handlers = [
        {
            "id": "message.handle",
            "module": "fixture_bot.handlers.message_handle",
            "symbol": "handle",
            "kind": "message",
        }
    ]
    flows = [
        {
            "schema_version": 3,
            "id": "main",
            "initial_state": "start",
            "states": {
                "start": {
                    "view": "home",
                    "on_message": {
                        "handler": "message.handle",
                        "outcomes": {"success": {"type": "noop"}},
                    },
                }
            },
        }
    ]
    make_project(tmp_path, handlers=handlers, flows=flows)
    write_handler(tmp_path, "fixture_bot.handlers.message_handle", source)

    diagnostics = validate_project(ProjectLoader().load(tmp_path), inspect_code=True)

    assert expected_code in {item.code for item in diagnostics}
