from __future__ import annotations

import keyword
import re
from pathlib import Path
from typing import Any

from tg_bot_core.project import (
    HandlerBinding,
    ProjectDefinition,
    find_handler_usages,
    inspect_handler_source,
)
from tg_bot_core.project.models import HANDLER_KINDS

from .repository import Workspace, WorkspaceError, WorkspaceRepository


_HANDLER_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*$")
_CONTEXTS = {
    "button": "ButtonContext",
    "message": "MessageContext",
    "command": "CommandContext",
    "lifecycle": "LifecycleContext",
    "task": "TaskContext",
}


def validate_handler_id(handler_id: str) -> tuple[str, ...]:
    if len(handler_id) > 128 or not _HANDLER_ID.fullmatch(handler_id):
        raise WorkspaceError(
            "Handler id must use dot-separated Python identifier segments."
        )
    parts = tuple(handler_id.split("."))
    if any(keyword.iskeyword(part) for part in parts):
        raise WorkspaceError("Handler id segments cannot be Python keywords.")
    return parts


def scaffold_target(workspace: Workspace, handler_id: str) -> tuple[str, Path]:
    parts = validate_handler_id(handler_id)
    module = ".".join((workspace.package, "handlers", *parts))
    relative = (
        Path("src").joinpath(*workspace.package.split("."), "handlers")
        / Path(*parts).with_suffix(".py")
    )
    return module, WorkspaceRepository.safe_path(workspace.root, relative, suffix=".py")


def handler_template(handler_id: str, kind: str) -> str:
    if kind not in HANDLER_KINDS:
        raise WorkspaceError(f"Unknown handler kind '{kind}'.")
    context = _CONTEXTS[kind]
    return f'''from tg_bot_core import {context}, HandlerResult


async def handle(ctx: {context}) -> HandlerResult:
    """Handle `{handler_id}`."""
    return HandlerResult.success()
'''


class HandlerInspector:
    def inspect(
        self,
        workspace: Workspace,
        binding: HandlerBinding,
        usages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        inspection = inspect_handler_source(
            workspace.root,
            workspace.package,
            binding,
        )
        source = (
            {
                "path": inspection.source_path,
                **({"line": inspection.line} if inspection.line else {}),
                **({"column": inspection.column} if inspection.column else {}),
            }
            if inspection.source_path
            else None
        )
        status = (
            "unused"
            if inspection.status == "ready" and not usages
            else inspection.status
        )
        return self._result(status, bool(usages), source, inspection.message)

    @staticmethod
    def _result(
        status: str,
        used: bool,
        source: dict[str, Any] | None,
        message: str | None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "used": used,
            "source": source,
            **({"message": message} if message else {}),
        }


def handler_usages(project: ProjectDefinition, handler_id: str) -> list[dict[str, Any]]:
    """Serialize the shared schema usage index for the Studio API."""

    return [usage.as_dict() for usage in find_handler_usages(project, handler_id)]
