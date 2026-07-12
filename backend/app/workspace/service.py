from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from jinja2 import Environment, TemplateSyntaxError

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,127}$")
_ACTION_TYPES = {"navigate", "flow.start", "flow.cancel", "flow.event"}
_JINJA = Environment()


class WorkspaceError(RuntimeError):
    status_code = 400
    code = "workspace_error"


class WorkspaceNotFound(WorkspaceError):
    status_code = 404
    code = "project_not_found"


class ResourceNotFound(WorkspaceError):
    status_code = 404
    code = "resource_not_found"


class RevisionConflict(WorkspaceError):
    status_code = 409
    code = "revision_conflict"


@dataclass(frozen=True, slots=True)
class Workspace:
    id: str
    root: Path
    resources: Path


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    _write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _safe_path(base: Path, relative: str, suffix: str) -> Path:
    raw = Path(relative)
    if not relative or raw.is_absolute() or ".." in raw.parts:
        raise WorkspaceError("Resource path must be a non-empty relative path.")
    target = (base / raw).resolve(strict=False)
    if not target.is_relative_to(base.resolve()) or target.suffix.lower() != suffix:
        raise WorkspaceError(f"Resource path must stay inside its root and end with {suffix}.")
    return target


class WorkspaceManager:
    """Studio v2 project filesystem: bot manifest, views and templates only."""

    def __init__(self) -> None:
        self._workspaces: dict[str, Workspace] = {}

    def open_project(self, root_path: str) -> dict[str, Any]:
        root = Path(root_path).expanduser().resolve(strict=False)
        resources = root / "resources"
        if not resources.is_dir() and (root / "bot.json").is_file():
            resources = root
            root = root.parent
        self._assert_structure(resources)
        workspace = Workspace(str(uuid4()), root, resources.resolve())
        self._workspaces[workspace.id] = workspace
        return self.describe(workspace.id)

    def create_starter(self, *, parent_path: str, name: str, package_name: str | None = None) -> dict[str, Any]:
        parent = Path(parent_path).expanduser().resolve(strict=False)
        if not parent.is_dir():
            raise WorkspaceError("Choose an existing parent directory.")
        parts = re.findall(r"[A-Za-z0-9]+", name.lower())
        if not parts:
            raise WorkspaceError("Project name must contain letters or digits.")
        slug, package = "-".join(parts), package_name or "_".join(parts)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", package):
            raise WorkspaceError("Package name must be a valid Python identifier.")
        root = parent / slug
        if root.exists():
            raise WorkspaceError(f"Project directory already exists: {slug}")
        resources = root / "resources"
        (resources / "views").mkdir(parents=True)
        (resources / "templates").mkdir()
        (root / "src" / package).mkdir(parents=True)
        (root / "data").mkdir()
        _write_json(resources / "bot.json", {"schema_version": 2, "entry_view": "home", "start_flow": "home"})
        _write_json(resources / "views" / "home.json", {"schema_version": 2, "id": "home", "text": {"template": "home.txt"}, "keyboard": []})
        _write(resources / "templates" / "home.txt", "Welcome to your bot!")
        _write(root / ".env.example", "BOT_TOKEN=\n")
        _write(root / ".gitignore", ".env\ndata/*.sqlite3\n__pycache__/\n")
        _write(root / "pyproject.toml", self._starter_pyproject(slug))
        _write(root / "src" / package / "__init__.py", "")
        _write(root / "src" / package / "flows.py", self._starter_flows())
        _write(root / "src" / package / "__main__.py", self._starter_main(package))
        return self.open_project(str(root))

    def describe(self, project_id: str) -> dict[str, Any]:
        workspace = self._workspace(project_id)
        views = [self._view_summary(workspace, path) for path in sorted((workspace.resources / "views").rglob("*.json"))]
        templates = [{"path": path.relative_to(workspace.resources / "templates").as_posix()} for path in sorted((workspace.resources / "templates").rglob("*.txt"))]
        return {"project_id": workspace.id, "name": workspace.root.name, "project_root": str(workspace.root), "resource_root": str(workspace.resources), "views": views, "templates": templates}

    def get_view(self, project_id: str, view_id: str) -> dict[str, Any]:
        workspace = self._workspace(project_id)
        path = self._view_path(workspace, view_id)
        return self._view_detail(workspace, path)

    def create_view(self, project_id: str, view_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        workspace = self._workspace(project_id)
        self._validate_id(view_id)
        if self._find_view(workspace, view_id):
            raise WorkspaceError(f"View '{view_id}' already exists.")
        path = workspace.resources / "views" / f"{view_id}.json"
        _write_json(path, payload)
        return self._view_detail(workspace, path)

    def save_view(self, project_id: str, view_id: str, payload: dict[str, Any], revision: str) -> dict[str, Any]:
        workspace = self._workspace(project_id)
        path = self._view_path(workspace, view_id)
        if _hash(path.read_bytes()) != revision:
            raise RevisionConflict("The view changed outside Studio. Reload from disk before saving.")
        _write_json(path, payload)
        return self._view_detail(workspace, path)

    def delete_view(self, project_id: str, view_id: str, revision: str) -> None:
        workspace = self._workspace(project_id)
        path = self._view_path(workspace, view_id)
        if _hash(path.read_bytes()) != revision:
            raise RevisionConflict("The view changed outside Studio. Reload from disk before deleting.")
        path.unlink()

    def get_template(self, project_id: str, path: str) -> dict[str, Any]:
        workspace = self._workspace(project_id)
        target = _safe_path(workspace.resources / "templates", path, ".txt")
        if not target.is_file():
            raise ResourceNotFound(f"Template '{path}' does not exist.")
        raw = target.read_bytes()
        return {"path": path, "content": raw.decode("utf-8"), "revision": _hash(raw)}

    def save_template(self, project_id: str, path: str, content: str, revision: str | None) -> dict[str, Any]:
        workspace = self._workspace(project_id)
        target = _safe_path(workspace.resources / "templates", path, ".txt")
        if target.exists() and revision != _hash(target.read_bytes()):
            raise RevisionConflict("The template changed outside Studio. Reload from disk before saving.")
        if not target.exists() and revision is not None:
            raise RevisionConflict("The template no longer exists.")
        _write(target, content)
        return self.get_template(project_id, path)

    def preview(self, project_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        workspace = self._workspace(project_id)
        warnings: list[str] = []
        text_config = payload.get("text")
        text = ""
        if not isinstance(text_config, dict):
            warnings.append("View text must be an object.")
        elif isinstance(text_config.get("inline"), str):
            text = text_config["inline"]
        elif isinstance(text_config.get("template"), str):
            try:
                text = _safe_path(workspace.resources / "templates", text_config["template"], ".txt").read_text(encoding="utf-8")
            except (OSError, WorkspaceError):
                warnings.append(f"Template '{text_config['template']}' is unavailable.")
        else:
            warnings.append("Text needs inline or template.")
        keyboard: list[list[dict[str, Any]]] = []
        for row in payload.get("keyboard", []) if isinstance(payload.get("keyboard", []), list) else []:
            if not isinstance(row, list):
                warnings.append("Keyboard row must be an array.")
                continue
            keyboard.append([{"text": button.get("text", "Untitled"), "action": button.get("action", {})} for button in row if isinstance(button, dict)])
        return {"text": text, "keyboard": keyboard, "warnings": warnings}

    def validate(self, project_id: str) -> list[dict[str, Any]]:
        workspace = self._workspace(project_id)
        issues: list[dict[str, Any]] = []
        try:
            self._assert_structure(workspace.resources)
            manifest = self._read_json(workspace.resources / "bot.json")
            if manifest.get("schema_version") != 2:
                issues.append(self._issue("error", "manifest_version", "bot.json must declare schema_version 2."))
            ids: set[str] = set()
            for path in (workspace.resources / "views").rglob("*.json"):
                data = self._read_json(path)
                view_id = data.get("id")
                source = path.relative_to(workspace.resources).as_posix()
                if not isinstance(view_id, str) or not _ID.fullmatch(view_id):
                    issues.append(self._issue("error", "view_id", "View id is invalid.", source))
                    continue
                if view_id in ids:
                    issues.append(self._issue("error", "view_duplicate", f"Duplicate view id '{view_id}'.", source))
                ids.add(view_id)
                if data.get("schema_version") != 2:
                    issues.append(self._issue("error", "view_version", "View must declare schema_version 2.", source))
                issues.extend(self._validate_view(workspace, data, source))
            entry = manifest.get("entry_view")
            if entry not in ids:
                issues.append(self._issue("error", "entry_view", "Manifest entry_view does not exist.", "bot.json"))
        except WorkspaceError as error:
            issues.append(self._issue("error", "structure", str(error)))
        return issues

    def _validate_view(self, workspace: Workspace, data: Mapping[str, Any], source: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        text = data.get("text")
        if not isinstance(text, dict) or ("inline" in text) == ("template" in text):
            return [self._issue("error", "text", "View text must contain exactly one of inline or template.", source)]
        template = text.get("template")
        raw = text.get("inline")
        if isinstance(template, str):
            try: raw = _safe_path(workspace.resources / "templates", template, ".txt").read_text(encoding="utf-8")
            except (OSError, WorkspaceError): issues.append(self._issue("error", "template", f"Missing template '{template}'.", source))
        if isinstance(raw, str):
            try: _JINJA.parse(raw)
            except TemplateSyntaxError as error: issues.append(self._issue("error", "jinja", str(error), source))
        keyboard = data.get("keyboard", [])
        if not isinstance(keyboard, list):
            return [*issues, self._issue("error", "keyboard", "Keyboard must be an array.", source)]
        for row in keyboard:
            if not isinstance(row, list):
                issues.append(self._issue("error", "keyboard", "Keyboard rows must be arrays.", source)); continue
            for button in row:
                action = button.get("action") if isinstance(button, dict) else None
                if not isinstance(button, dict) or not isinstance(button.get("text"), str) or not isinstance(action, dict):
                    issues.append(self._issue("error", "button", "Invalid keyboard button.", source)); continue
                action_type, target = action.get("type"), action.get("target")
                if action_type not in _ACTION_TYPES:
                    issues.append(self._issue("error", "action", "Invalid action type.", source)); continue
                if action_type in {"navigate", "flow.start", "flow.event"} and not isinstance(target, str):
                    issues.append(self._issue("error", "action_target", "Action target is required.", source))
                encoded = f"v2:{ {'navigate':'n','flow.start':'s','flow.cancel':'c','flow.event':'e'}[action_type] }:{target or ''}"
                if len(encoded.encode("utf-8")) > 64:
                    issues.append(self._issue("error", "callback_length", "Action exceeds Telegram's callback limit.", source))
                if action_type == "flow.start":
                    issues.append(self._issue("warning", "flow_binding", "Python flow binding is not indexed by Studio yet.", source))
        return issues

    def _workspace(self, project_id: str) -> Workspace:
        workspace = self._workspaces.get(project_id)
        if workspace is None: raise WorkspaceNotFound("Project is not open.")
        return workspace

    def _find_view(self, workspace: Workspace, view_id: str) -> Path | None:
        for path in (workspace.resources / "views").rglob("*.json"):
            try:
                if self._read_json(path).get("id") == view_id: return path
            except WorkspaceError: continue
        return None

    def _view_path(self, workspace: Workspace, view_id: str) -> Path:
        path = self._find_view(workspace, view_id)
        if path is None: raise ResourceNotFound(f"View '{view_id}' does not exist.")
        return path

    def _view_summary(self, workspace: Workspace, path: Path) -> dict[str, Any]:
        detail = self._view_detail(workspace, path)
        return {key: detail[key] for key in ("id", "source_path", "revision")}

    def _view_detail(self, workspace: Workspace, path: Path) -> dict[str, Any]:
        raw = path.read_bytes(); payload = self._read_json(path)
        view_id = payload.get("id")
        if not isinstance(view_id, str): raise WorkspaceError(f"View id is missing: {path}")
        return {"id": view_id, "source_path": path.relative_to(workspace.resources).as_posix(), "revision": _hash(raw), "payload": payload}

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try: data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error: raise WorkspaceError(f"Invalid JSON: {path}") from error
        if not isinstance(data, dict): raise WorkspaceError(f"JSON must be an object: {path}")
        return data

    @staticmethod
    def _assert_structure(resources: Path) -> None:
        required = (resources / "bot.json", resources / "views", resources / "templates")
        if not required[0].is_file() or not required[1].is_dir() or not required[2].is_dir():
            raise WorkspaceError("A v2 project needs resources/bot.json, resources/views and resources/templates.")

    @staticmethod
    def _validate_id(view_id: str) -> None:
        if not _ID.fullmatch(view_id): raise WorkspaceError("View id must start with a letter and contain only letters, numbers, _ or -.")

    @staticmethod
    def _issue(level: str, code: str, message: str, source_path: str | None = None) -> dict[str, Any]:
        return {"level": level, "code": code, "message": message, **({"source_path": source_path} if source_path else {})}

    @staticmethod
    def _starter_pyproject(slug: str) -> str:
        return f'''[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{slug}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["tg-bot-core @ git+https://github.com/SnailCap/TG_bots.git@core-v2.0.0#subdirectory=packages/tg-bot-core"]

[tool.setuptools]
package-dir = {{"" = "src"}}
[tool.setuptools.packages.find]
where = ["src"]
'''

    @staticmethod
    def _starter_flows() -> str:
        return '''from tg_bot_core import FlowDefinition, FlowState, Transition


async def show_home(ctx, event):
    return Transition.render("home")


flows = [FlowDefinition("home", "start", {"start": FlowState("start", on_enter=show_home)})]
'''

    @staticmethod
    def _starter_main(package: str) -> str:
        return f'''from pathlib import Path

from tg_bot_core import BotApp, BotConfig, BotModule
from {package}.flows import flows


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    BotApp(config=BotConfig.from_env(bot_id="{package}", resource_root=root / "resources", database_path=root / "data" / "runtime.sqlite3"), module=BotModule(flows=flows)).run()


if __name__ == "__main__":
    main()
'''
