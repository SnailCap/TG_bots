from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tg_bot_core.events import InteractionEvent
from tg_bot_core.transport import EventHandler, OutboundMessage


class FakeTransport:
    """In-memory transport used by runtime and standalone acceptance tests."""

    def __init__(self) -> None:
        self.handler: EventHandler | None = None
        self.messages: list[OutboundMessage] = []
        self.started = False
        self.stopped = False

    async def start(self, handler: EventHandler) -> None:
        self.handler = handler
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send(self, message: OutboundMessage) -> None:
        self.messages.append(message)

    async def emit(self, event: InteractionEvent) -> None:
        if self.handler is None:
            raise RuntimeError("Fake transport has not been started.")
        await self.handler(event)


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_handler(project_root: Path, module: str, source: str) -> Path:
    parts = module.split(".")
    package_root = project_root / "src"
    for depth in range(1, len(parts)):
        package = package_root.joinpath(*parts[:depth])
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").touch()
    path = package_root.joinpath(*parts).with_suffix(".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def make_project(
    root: Path,
    *,
    bot: Mapping[str, Any] | None = None,
    views: Sequence[Mapping[str, Any]] | None = None,
    flows: Sequence[Mapping[str, Any]] | None = None,
    handlers: Sequence[Mapping[str, Any]] = (),
    commands: Mapping[str, Any] | None = None,
    schedules: Sequence[Mapping[str, Any]] = (),
    templates: Mapping[str, str] | None = None,
) -> Path:
    resources = root / "resources"
    (resources / "views").mkdir(parents=True, exist_ok=True)
    (resources / "flows").mkdir(parents=True, exist_ok=True)
    (resources / "schedules").mkdir(parents=True, exist_ok=True)
    (resources / "templates").mkdir(parents=True, exist_ok=True)
    package = str((bot or {}).get("package", "fixture_bot"))
    package_dir = root / "src" / package
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").touch()

    manifest = {
        "schema_version": 3,
        "id": "fixture-bot",
        "package": package,
        "entry_view": "home",
        "start": {"flow": "main", "policy": "reset"},
        **dict(bot or {}),
    }
    view_values = list(
        views
        or [
            {
                "schema_version": 3,
                "id": "home",
                "text": {"inline": "Home"},
                "keyboard": [],
            }
        ]
    )
    flow_values = list(
        flows
        or [
            {
                "schema_version": 3,
                "id": "main",
                "initial_state": "start",
                "states": {"start": {"view": "home"}},
            }
        ]
    )

    write_json(resources / "bot.json", manifest)
    write_json(resources / "handlers.json", {"schema_version": 3, "handlers": list(handlers)})
    write_json(
        resources / "commands.json",
        {"schema_version": 3, "commands": [], **dict(commands or {})},
    )
    for view in view_values:
        write_json(resources / "views" / f"{view['id']}.json", view)
    for flow in flow_values:
        write_json(resources / "flows" / f"{flow['id']}.json", flow)
    for schedule in schedules:
        write_json(resources / "schedules" / f"{schedule['id']}.json", schedule)
    for relative, text in (templates or {}).items():
        path = resources / "templates" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root
