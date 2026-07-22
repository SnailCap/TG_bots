from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, TemplateSyntaxError
from tg_bot_core.events import UserRole
from tg_bot_core.project import (
    ProjectLoadError,
    ProjectLoader,
    load_and_validate_project,
    validate_project,
)
from tg_bot_core.store import BotUser, SqliteStore, StoredUserAvatar

from .handlers import (
    HandlerInspector,
    handler_template,
    handler_usages,
    scaffold_target,
    validate_handler_id,
)
from .repository import (
    ResourceConflict,
    ResourceInUse,
    ResourceNotFound,
    RevisionConflict,
    Workspace,
    WorkspaceError,
    WorkspaceNotFound,
    WorkspaceRepository,
    content_revision,
)
from .starter import StarterScaffolder


_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,127}$")
_RESOURCE_KINDS = {"views", "flows", "schedules"}
_JINJA = Environment()
_ENV_ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
_TELEGRAM_TOKEN_MAX_LENGTH = 4096


class ProjectService:
    """Application service for Studio; schema semantics stay in tg_bot_core.project."""

    def __init__(
        self,
        *,
        loader: ProjectLoader | None = None,
        repository: WorkspaceRepository | None = None,
    ) -> None:
        self.loader = loader or ProjectLoader()
        self.repository = repository or WorkspaceRepository(self.loader)
        self.starter = StarterScaffolder(self.loader)
        self.inspector = HandlerInspector()

    def open_project(self, root_path: str) -> dict[str, Any]:
        return self.describe(self.repository.open(root_path).id)

    def create_starter(
        self,
        *,
        parent_path: str,
        name: str,
        package_name: str | None = None,
    ) -> dict[str, Any]:
        root = self.starter.create(
            parent_path=parent_path,
            name=name,
            package_name=package_name,
        )
        identity = self._directory_identity(root)
        opened: Workspace | None = None
        try:
            opened = self.repository.open(root)
            return self.describe(opened.id)
        except BaseException:
            if opened is not None:
                self.repository.forget(opened.id)
            self._remove_created_directory(root, identity)
            raise

    def describe(self, project_id: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        project = self._load(workspace)
        manifest = self.repository.detail(
            workspace.resources / "bot.json", resource_root=workspace.resources
        )
        commands = self.repository.detail(
            workspace.resources / "commands.json", resource_root=workspace.resources
        )
        handlers_path = workspace.resources / "handlers.json"
        return {
            "project_id": workspace.id,
            "name": workspace.root.name,
            "package": workspace.package,
            "schema_version": 3,
            "project_root": str(workspace.root),
            "resource_root": str(workspace.resources),
            "manifest": manifest,
            "commands": {
                key: commands[key] for key in ("source_path", "revision")
            },
            "handlers_revision": content_revision(handlers_path.read_bytes()),
            "views": self._catalog_summaries(workspace, project.views.values()),
            "flows": self._catalog_summaries(workspace, project.flows.values()),
            "schedules": self._catalog_summaries(workspace, project.schedules.values()),
            "handlers": self._handler_summaries(workspace, project),
            "templates": [
                {"path": path.relative_to(workspace.resources / "templates").as_posix()}
                for path in sorted((workspace.resources / "templates").rglob("*.txt"))
            ],
        }

    async def list_users(self, project_id: str) -> list[dict[str, Any]]:
        workspace, bot_id, store = await self._user_store(project_id)
        del workspace
        return [self._user_detail(user) for user in await store.list_users(bot_id)]

    async def update_user(
        self,
        project_id: str,
        user_id: int,
        *,
        role: UserRole,
        blocked: bool,
        note: str,
    ) -> dict[str, Any]:
        _workspace, bot_id, store = await self._user_store(project_id)
        try:
            user = await store.update_user(
                bot_id, user_id, role=role, blocked=blocked, note=note
            )
        except ValueError as error:
            raise WorkspaceError(str(error)) from error
        if user is None:
            raise ResourceNotFound(f"User '{user_id}' does not exist.")
        return self._user_detail(user)

    async def get_user_avatar(
        self, project_id: str, user_id: int
    ) -> StoredUserAvatar:
        _workspace, bot_id, store = await self._user_store(project_id)
        avatar = await store.get_user_avatar(bot_id, user_id)
        if avatar is None:
            raise ResourceNotFound(f"User '{user_id}' does not have a profile photo.")
        return avatar

    # Project runtime settings ---------------------------------------------------------

    def get_project_settings(self, project_id: str) -> dict[str, Any]:
        """Return project-local runtime setting metadata without exposing secrets."""

        workspace = self.repository.workspace(project_id)
        path = self.repository.safe_path(workspace.root, ".env")
        content = self._read_environment(path) if path.exists() else ""
        token = self._environment_value(content, "BOT_TOKEN")
        return {
            "telegram_bot_token_configured": bool(token),
            "revision": content_revision(path.read_bytes()) if path.exists() else None,
        }

    def save_project_settings(
        self,
        project_id: str,
        *,
        telegram_bot_token: str | None,
        clear_telegram_bot_token: bool,
        revision: str | None,
    ) -> dict[str, Any]:
        if telegram_bot_token is not None and clear_telegram_bot_token:
            raise WorkspaceError("Set a token or clear it, but not both in one request.")
        if telegram_bot_token is None and not clear_telegram_bot_token:
            raise WorkspaceError("Provide a Telegram bot token or choose to clear it.")

        normalized_token = None
        if telegram_bot_token is not None:
            normalized_token = self._normalize_telegram_token(telegram_bot_token)

        workspace = self.repository.workspace(project_id)
        path = self.repository.safe_path(workspace.root, ".env")
        with self.repository.lock(workspace):
            if clear_telegram_bot_token and not path.exists():
                return self.get_project_settings(project_id)
            self.repository.assert_revision(path, revision, creating=not path.exists())
            previous = self._read_environment(path) if path.exists() else ""
            updated = self._replace_environment_value(
                previous,
                "BOT_TOKEN",
                None if clear_telegram_bot_token else normalized_token,
            )
            environment_before = path.read_bytes() if path.exists() else None
            gitignore = self.repository.safe_path(workspace.root, ".gitignore")
            gitignore_before = gitignore.read_bytes() if gitignore.exists() else None
            try:
                self.repository.atomic_write(path, updated.encode("utf-8"))
                if normalized_token is not None:
                    self._ensure_environment_is_ignored(gitignore)
            except BaseException:
                self.repository.restore(path, environment_before)
                self.repository.restore(gitignore, gitignore_before)
                raise
        return self.get_project_settings(project_id)

    # Manifest and aggregate resources -------------------------------------------------

    def get_manifest(self, project_id: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        return self.repository.detail(
            workspace.resources / "bot.json", resource_root=workspace.resources
        )

    def save_manifest(
        self,
        project_id: str,
        payload: dict[str, Any],
        revision: str,
    ) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        if payload.get("package") != workspace.package:
            raise WorkspaceError("Changing the project Python package is not supported by Studio.")
        normalized = dict(payload)
        normalized["schema_version"] = 3
        path = workspace.resources / "bot.json"
        self._save_json_and_parse(workspace, path, normalized, revision)
        return self.get_manifest(project_id)

    def get_commands(self, project_id: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        return self.repository.detail(
            workspace.resources / "commands.json", resource_root=workspace.resources
        )

    def save_commands(
        self,
        project_id: str,
        payload: dict[str, Any],
        revision: str,
    ) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        normalized = dict(payload)
        normalized["schema_version"] = 3
        normalized.setdefault("commands", [])
        path = workspace.resources / "commands.json"
        self._save_json_and_parse(workspace, path, normalized, revision)
        return self.get_commands(project_id)

    # File-per-entity resources --------------------------------------------------------

    def list_views(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_resources(project_id, "views")

    def list_flows(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_resources(project_id, "flows")

    def list_schedules(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_resources(project_id, "schedules")

    def get_view(self, project_id: str, view_id: str) -> dict[str, Any]:
        return self._get_resource(project_id, "views", view_id)

    def get_flow(self, project_id: str, flow_id: str) -> dict[str, Any]:
        return self._get_resource(project_id, "flows", flow_id)

    def get_schedule(self, project_id: str, schedule_id: str) -> dict[str, Any]:
        return self._get_resource(project_id, "schedules", schedule_id)

    def create_view(self, project_id: str, view_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create_resource(project_id, "views", view_id, payload)

    def create_flow(self, project_id: str, flow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._create_resource(project_id, "flows", flow_id, payload)

    def create_schedule(
        self, project_id: str, schedule_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._create_resource(project_id, "schedules", schedule_id, payload)

    def save_view(
        self, project_id: str, view_id: str, payload: dict[str, Any], revision: str
    ) -> dict[str, Any]:
        return self._save_resource(project_id, "views", view_id, payload, revision)

    def rename_view(
        self, project_id: str, view_id: str, new_id: str, revision: str
    ) -> dict[str, Any]:
        self._validate_resource_id(new_id)
        if view_id == new_id:
            return self.get_view(project_id, view_id)
        workspace = self.repository.workspace(project_id)
        with self.repository.lock(workspace):
            project = self._load(workspace)
            source = self._entity_path(workspace, project, "views", view_id)
            target = self.repository.safe_path(
                workspace.resources, Path("views") / f"{new_id}.json", suffix=".json"
            )
            if new_id in project.views or target.exists():
                raise ResourceConflict(f"View '{new_id}' already exists.")
            self.repository.assert_revision(source, revision)
            documents = [
                workspace.resources / "bot.json",
                workspace.resources / "commands.json",
                *(self._entity_path(workspace, project, "views", item.id) for item in project.views.values()),
                *(self._entity_path(workspace, project, "flows", item.id) for item in project.flows.values()),
            ]
            payloads = {path: self.repository.read_json(path) for path in documents}
            payloads[source]["id"] = new_id
            manifest = payloads[workspace.resources / "bot.json"]
            if manifest.get("entry_view") == view_id:
                manifest["entry_view"] = new_id
            for payload in payloads.values():
                self._replace_view_reference(payload, view_id, new_id)
            before = {path: path.read_bytes() for path in payloads}
            try:
                for path, payload in payloads.items():
                    self.repository.atomic_write_json(target if path == source else path, payload)
                source.unlink()
                self._load(workspace)
            except BaseException:
                target.unlink(missing_ok=True)
                for path, content in before.items():
                    self.repository.restore(path, content)
                raise
        return self.get_view(project_id, new_id)

    def save_flow(
        self, project_id: str, flow_id: str, payload: dict[str, Any], revision: str
    ) -> dict[str, Any]:
        return self._save_resource(project_id, "flows", flow_id, payload, revision)

    def rename_flow(
        self, project_id: str, flow_id: str, new_id: str, revision: str
    ) -> dict[str, Any]:
        self._validate_resource_id(new_id)
        if flow_id == new_id:
            return self.get_flow(project_id, flow_id)
        workspace = self.repository.workspace(project_id)
        with self.repository.lock(workspace):
            project = self._load(workspace)
            source = self._entity_path(workspace, project, "flows", flow_id)
            target = self.repository.safe_path(
                workspace.resources, Path("flows") / f"{new_id}.json", suffix=".json"
            )
            if new_id in project.flows or target.exists():
                raise ResourceConflict(f"Flow '{new_id}' already exists.")
            self.repository.assert_revision(source, revision)
            documents = [
                workspace.resources / "bot.json",
                workspace.resources / "commands.json",
                *(self._entity_path(workspace, project, "views", item.id) for item in project.views.values()),
                *(self._entity_path(workspace, project, "flows", item.id) for item in project.flows.values()),
            ]
            payloads = {path: self.repository.read_json(path) for path in documents}
            payloads[source]["id"] = new_id
            manifest = payloads[workspace.resources / "bot.json"]
            if manifest.get("start", {}).get("flow") == flow_id:
                manifest["start"]["flow"] = new_id
            for payload in payloads.values():
                self._replace_flow_reference(payload, flow_id, new_id)
            before = {path: path.read_bytes() for path in payloads}
            try:
                for path, payload in payloads.items():
                    self.repository.atomic_write_json(target if path == source else path, payload)
                source.unlink()
                self._load(workspace)
            except BaseException:
                target.unlink(missing_ok=True)
                for path, content in before.items():
                    self.repository.restore(path, content)
                raise
        return self.get_flow(project_id, new_id)

    def save_schedule(
        self, project_id: str, schedule_id: str, payload: dict[str, Any], revision: str
    ) -> dict[str, Any]:
        return self._save_resource(project_id, "schedules", schedule_id, payload, revision)

    def rename_schedule(
        self, project_id: str, schedule_id: str, new_id: str, revision: str
    ) -> dict[str, Any]:
        self._validate_resource_id(new_id)
        if schedule_id == new_id:
            return self.get_schedule(project_id, schedule_id)
        workspace = self.repository.workspace(project_id)
        with self.repository.lock(workspace):
            project = self._load(workspace)
            source = self._entity_path(workspace, project, "schedules", schedule_id)
            target = self.repository.safe_path(
                workspace.resources, Path("schedules") / f"{new_id}.json", suffix=".json"
            )
            if new_id in project.schedules or target.exists():
                raise ResourceConflict(f"Schedule '{new_id}' already exists.")
            self.repository.assert_revision(source, revision)
            payload = self.repository.read_json(source)
            payload["id"] = new_id
            before = source.read_bytes()
            try:
                self.repository.atomic_write_json(target, payload)
                source.unlink()
                self._load(workspace)
            except BaseException:
                target.unlink(missing_ok=True)
                self.repository.restore(source, before)
                raise
        return self.get_schedule(project_id, new_id)

    def delete_view(self, project_id: str, view_id: str, revision: str) -> None:
        self._delete_resource(project_id, "views", view_id, revision)

    def delete_flow(self, project_id: str, flow_id: str, revision: str) -> None:
        self._delete_resource(project_id, "flows", flow_id, revision)

    def delete_schedule(self, project_id: str, schedule_id: str, revision: str) -> None:
        self._delete_resource(project_id, "schedules", schedule_id, revision)

    # Templates and preview ------------------------------------------------------------

    def get_template(self, project_id: str, path: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        target = self.repository.safe_path(
            workspace.resources / "templates", path, suffix=".txt"
        )
        if not target.is_file():
            raise ResourceNotFound(f"Template '{path}' does not exist.")
        raw = target.read_bytes()
        return {"path": path, "content": raw.decode("utf-8"), "revision": content_revision(raw)}

    def save_template(
        self,
        project_id: str,
        path: str,
        content: str,
        revision: str | None,
    ) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        target = self.repository.safe_path(
            workspace.resources / "templates", path, suffix=".txt"
        )
        with self.repository.lock(workspace):
            creating = not target.exists()
            self.repository.assert_revision(target, revision, creating=creating)
            self.repository.atomic_write(target, content.encode("utf-8"))
        return self.get_template(project_id, path)

    def rename_template(
        self, project_id: str, path: str, new_path: str, revision: str
    ) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        source = self.repository.safe_path(
            workspace.resources / "templates", path, suffix=".txt"
        )
        target = self.repository.safe_path(
            workspace.resources / "templates", new_path, suffix=".txt"
        )
        if path == new_path:
            return self.get_template(project_id, path)
        with self.repository.lock(workspace):
            self.repository.assert_revision(source, revision)
            if not source.is_file():
                raise ResourceNotFound(f"Template '{path}' does not exist.")
            if target.exists():
                raise ResourceConflict(f"Template '{new_path}' already exists.")
            project = self._load(workspace)
            documents = [
                self._entity_path(workspace, project, "views", view.id)
                for view in project.views.values()
                if view.text.template == path
            ]
            payloads = {item: self.repository.read_json(item) for item in documents}
            for payload in payloads.values():
                payload["text"]["template"] = new_path
            before = {source: source.read_bytes(), **{item: item.read_bytes() for item in payloads}}
            try:
                self.repository.atomic_write(target, before[source])
                for item, payload in payloads.items():
                    self.repository.atomic_write_json(item, payload)
                source.unlink()
                self._load(workspace)
            except BaseException:
                target.unlink(missing_ok=True)
                for item, content in before.items():
                    self.repository.restore(item, content)
                raise
        return self.get_template(project_id, new_path)

    def delete_template(self, project_id: str, path: str, revision: str) -> None:
        workspace = self.repository.workspace(project_id)
        target = self.repository.safe_path(
            workspace.resources / "templates", path, suffix=".txt"
        )
        with self.repository.lock(workspace):
            self.repository.assert_revision(target, revision)
            project = self._load(workspace)
            usages = [
                view.source_path or view.id
                for view in project.views.values()
                if view.text.template == path
            ]
            if usages:
                raise ResourceInUse(
                    f"Template '{path}' is still referenced {len(usages)} time(s)."
                )
            before = target.read_bytes()
            try:
                target.unlink()
                self._load(workspace)
            except BaseException:
                self.repository.restore(target, before)
                raise

    def preview(self, project_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        warnings: list[str] = []
        text_config = payload.get("text")
        text = ""
        if not isinstance(text_config, dict):
            warnings.append("View text must be an object.")
        elif isinstance(text_config.get("inline"), str):
            text = text_config["inline"]
        elif isinstance(text_config.get("template"), str):
            try:
                text = self.repository.safe_path(
                    workspace.resources / "templates",
                    text_config["template"],
                    suffix=".txt",
                ).read_text(encoding="utf-8")
            except (OSError, WorkspaceError):
                warnings.append(f"Template '{text_config['template']}' is unavailable.")
        else:
            warnings.append("Text needs exactly one of inline or template.")
        if text:
            try:
                _JINJA.parse(text)
            except TemplateSyntaxError as error:
                warnings.append(str(error))
        keyboard: list[list[dict[str, Any]]] = []
        rows = payload.get("keyboard", [])
        if not isinstance(rows, list):
            warnings.append("Keyboard must be an array.")
            rows = []
        for row in rows:
            if not isinstance(row, list):
                warnings.append("Keyboard row must be an array.")
                continue
            keyboard.append(
                [
                    {
                        "id": button.get("id"),
                        "text": button.get("text", "Untitled"),
                        "action": button.get("action", {}),
                    }
                    for button in row
                    if isinstance(button, dict)
                ]
            )
        return {"text": text, "keyboard": keyboard, "warnings": warnings}

    @staticmethod
    def _read_environment(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise WorkspaceError("Cannot read the project .env file as UTF-8.") from error

    @staticmethod
    def _environment_value(content: str, key: str) -> str | None:
        value: str | None = None
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = _ENV_ASSIGNMENT.match(line)
            if match is None or match.group(1) != key:
                continue
            candidate = match.group(2).strip()
            if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {"'", '"'}:
                candidate = candidate[1:-1]
            value = candidate or None
        return value

    @staticmethod
    def _replace_environment_value(content: str, key: str, value: str | None) -> str:
        lines = [
            line
            for line in content.splitlines()
            if (match := _ENV_ASSIGNMENT.match(line)) is None or match.group(1) != key
        ]
        if value is not None:
            lines.append(f"{key}={value}")
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _ensure_environment_is_ignored(path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8") if path.exists() else ""
        except (OSError, UnicodeError) as error:
            raise WorkspaceError("Cannot read the project .gitignore file as UTF-8.") from error
        entries = {line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")}
        if {".env", "/.env", "*.env"} & entries:
            return
        suffix = "" if not content or content.endswith("\n") else "\n"
        WorkspaceRepository.atomic_write(path, f"{content}{suffix}.env\n".encode("utf-8"))

    @staticmethod
    def _normalize_telegram_token(value: str) -> str:
        if value != value.strip() or not value:
            raise WorkspaceError("Telegram bot token cannot be empty or contain leading/trailing whitespace.")
        if len(value) > _TELEGRAM_TOKEN_MAX_LENGTH or any(character.isspace() for character in value):
            raise WorkspaceError("Telegram bot token must be a single non-whitespace value.")
        return value

    # Handlers ------------------------------------------------------------------------

    def list_handlers(self, project_id: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        project = self._load(workspace)
        path = workspace.resources / "handlers.json"
        return {
            "revision": content_revision(path.read_bytes()),
            "handlers": self._handler_summaries(workspace, project),
        }

    def get_handler(self, project_id: str, handler_id: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        project = self._load(workspace)
        try:
            binding = project.handlers[handler_id]
        except KeyError as error:
            raise ResourceNotFound(f"Handler '{handler_id}' does not exist.") from error
        usages = handler_usages(project, handler_id)
        registry_path = workspace.resources / "handlers.json"
        return {
            **self._binding_payload(binding),
            "source_path": "handlers.json",
            "revision": content_revision(registry_path.read_bytes()),
            "inspection": self.inspector.inspect(workspace, binding, usages),
            "usages": usages,
        }

    def rename_handler(
        self, project_id: str, handler_id: str, new_id: str, revision: str
    ) -> dict[str, Any]:
        validate_handler_id(new_id)
        if handler_id == new_id:
            return self.get_handler(project_id, handler_id)
        workspace = self.repository.workspace(project_id)
        registry_path = workspace.resources / "handlers.json"
        with self.repository.lock(workspace):
            self.repository.assert_revision(registry_path, revision)
            project = self._load(workspace)
            if handler_id not in project.handlers:
                raise ResourceNotFound(f"Handler '{handler_id}' does not exist.")
            if new_id in project.handlers:
                raise ResourceConflict(f"Handler '{new_id}' already exists.")
            documents = [
                registry_path,
                workspace.resources / "commands.json",
                *(self._entity_path(workspace, project, "views", item.id) for item in project.views.values()),
                *(self._entity_path(workspace, project, "flows", item.id) for item in project.flows.values()),
                *(self._entity_path(workspace, project, "schedules", item.id) for item in project.schedules.values()),
            ]
            payloads = {path: self.repository.read_json(path) for path in documents}
            bindings = payloads[registry_path].get("handlers")
            if not isinstance(bindings, list):
                raise WorkspaceError("handlers.json: handlers must be an array.")
            for binding in bindings:
                if isinstance(binding, dict) and binding.get("id") == handler_id:
                    binding["id"] = new_id
                    break
            else:
                raise ResourceNotFound(f"Handler '{handler_id}' does not exist.")
            for path, payload in payloads.items():
                if path != registry_path:
                    self._replace_handler_reference(payload, handler_id, new_id)
            before = {path: path.read_bytes() for path in payloads}
            try:
                for path, payload in payloads.items():
                    self.repository.atomic_write_json(path, payload)
                self._load(workspace)
            except BaseException:
                for path, content in before.items():
                    self.repository.restore(path, content)
                raise
        return self.get_handler(project_id, new_id)

    def handler_usages(self, project_id: str, handler_id: str) -> list[dict[str, Any]]:
        detail = self.get_handler(project_id, handler_id)
        return detail["usages"]

    def handler_source(self, project_id: str, handler_id: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        detail = self.get_handler(project_id, handler_id)
        source = detail["inspection"].get("source")
        if not isinstance(source, dict) or not isinstance(source.get("path"), str):
            raise WorkspaceError("Handler binding does not resolve to a safe source path.")
        absolute = self.repository.safe_path(workspace.root, source["path"], suffix=".py")
        if not absolute.is_file():
            raise ResourceNotFound(f"Handler source file does not exist: {source['path']}")
        return {
            "project_root": str(workspace.root),
            "file_path": str(absolute),
            "source_path": source["path"],
            "line": source.get("line", 1),
            "column": source.get("column", 1),
        }

    def scaffold_handler(
        self,
        project_id: str,
        *,
        handler_id: str,
        kind: str,
        outcomes: list[str],
        description: str | None,
        registry_revision: str,
        attachment: Mapping[str, Any] | None = None,
        target_revision: str | None = None,
        routes: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        module, source_path = scaffold_target(workspace, handler_id)
        source_template = handler_template(handler_id, kind)
        if len(set(outcomes)) != len(outcomes) or any(
            not isinstance(value, str) or not value.strip() for value in outcomes
        ):
            raise WorkspaceError("Handler outcomes must be unique non-empty strings.")
        route_map = dict(routes or {})
        if attachment:
            route_map.setdefault("success", {"type": "noop"})
        missing_routes = set(outcomes) - set(route_map)
        if attachment and missing_routes:
            raise WorkspaceError(
                "Attachment is missing routes for outcomes: " + ", ".join(sorted(missing_routes))
            )

        registry_path = workspace.resources / "handlers.json"
        registry_before: bytes | None = None
        target_path: Path | None = None
        target_before: bytes | None = None
        file_created = False
        created_initializers: list[Path] = []
        with self.repository.lock(workspace):
            self.repository.assert_revision(registry_path, registry_revision)
            registry_before = registry_path.read_bytes()
            registry = self.repository.read_json(registry_path)
            bindings = registry.get("handlers")
            if not isinstance(bindings, list):
                raise WorkspaceError("handlers.json: handlers must be an array.")
            if any(isinstance(value, dict) and value.get("id") == handler_id for value in bindings):
                raise ResourceConflict(f"Handler '{handler_id}' already exists.")

            project = self._load(workspace)
            attachment_payload: dict[str, Any] | None = None
            expected_kind: str | None = None
            if attachment:
                target_path, attachment_payload, expected_kind = self._attachment_document(
                    workspace, project, attachment, handler_id, route_map
                )
                if expected_kind != kind:
                    raise WorkspaceError(
                        f"Attachment requires handler kind '{expected_kind}', got '{kind}'."
                    )
                if target_revision is None:
                    raise WorkspaceError("target_revision is required when attaching a handler.")
                self.repository.assert_revision(target_path, target_revision)
                target_before = target_path.read_bytes()

            binding: dict[str, Any] = {
                "id": handler_id,
                "module": module,
                "symbol": "handle",
                "kind": kind,
                "outcomes": list(outcomes),
            }
            if description:
                binding["description"] = description
            updated_registry = dict(registry)
            updated_registry["schema_version"] = 3
            updated_registry["handlers"] = [*bindings, binding]

            try:
                created_initializers = self._ensure_handler_packages(workspace, source_path.parent)
                file_created = self.repository.create_exclusive(
                    source_path, source_template
                )
                self.repository.atomic_write_json(registry_path, updated_registry)
                if target_path is not None and attachment_payload is not None:
                    self.repository.atomic_write_json(target_path, attachment_payload)
                candidate = self._load(workspace)
                errors = [
                    item
                    for item in validate_project(candidate, inspect_code=True)
                    if item.level == "error"
                ]
                if errors:
                    raise WorkspaceError(
                        "Handler scaffold would leave the project invalid: "
                        + "; ".join(item.message for item in errors)
                    )
            except BaseException:
                if target_path is not None and target_before is not None:
                    self.repository.restore(target_path, target_before)
                if registry_before is not None:
                    self.repository.restore(registry_path, registry_before)
                if file_created:
                    source_path.unlink(missing_ok=True)
                for initializer in reversed(created_initializers):
                    try:
                        if initializer.read_text(encoding="utf-8") == "":
                            initializer.unlink()
                    except OSError:
                        pass
                raise

        detail = self.get_handler(project_id, handler_id)
        detail["file_created"] = file_created
        detail["open_target"] = self.handler_source(project_id, handler_id)
        return detail

    def repair_handler(
        self,
        project_id: str,
        handler_id: str,
        *,
        registry_revision: str,
    ) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        registry_path = workspace.resources / "handlers.json"
        created_initializers: list[Path] = []
        file_created = False

        with self.repository.lock(workspace):
            self.repository.assert_revision(registry_path, registry_revision)
            project = self._load(workspace)
            try:
                binding = project.handlers[handler_id]
            except KeyError as error:
                raise ResourceNotFound(
                    f"Handler '{handler_id}' does not exist."
                ) from error

            canonical_module, source_path = scaffold_target(workspace, handler_id)
            if binding.module != canonical_module:
                raise WorkspaceError(
                    f"Handler '{handler_id}' does not use its canonical Studio module "
                    f"'{canonical_module}'."
                )
            if binding.symbol != "handle":
                raise WorkspaceError(
                    f"Handler '{handler_id}' must use the Studio symbol 'handle'."
                )
            source_template = handler_template(handler_id, binding.kind)

            if source_path.exists():
                raise ResourceConflict(
                    f"Handler source already exists: "
                    f"{source_path.relative_to(workspace.root).as_posix()}"
                )

            try:
                created_initializers = self._ensure_handler_packages(
                    workspace, source_path.parent
                )
                file_created = self.repository.create_exclusive(
                    source_path, source_template
                )
                if not file_created:
                    raise ResourceConflict(
                        "Handler source was created outside Studio. Reload the project."
                    )
                candidate = self._load(workspace)
                errors = [
                    item
                    for item in validate_project(candidate, inspect_code=True)
                    if item.level == "error"
                ]
                if errors:
                    raise WorkspaceError(
                        "Handler repair would leave the project invalid: "
                        + "; ".join(item.message for item in errors)
                    )
            except BaseException:
                if file_created:
                    source_path.unlink(missing_ok=True)
                for initializer in reversed(created_initializers):
                    try:
                        if initializer.read_text(encoding="utf-8") == "":
                            initializer.unlink()
                    except OSError:
                        pass
                raise

        detail = self.get_handler(project_id, handler_id)
        detail["file_created"] = True
        detail["open_target"] = self.handler_source(project_id, handler_id)
        return detail

    def delete_handler(self, project_id: str, handler_id: str, revision: str) -> None:
        workspace = self.repository.workspace(project_id)
        registry_path = workspace.resources / "handlers.json"
        with self.repository.lock(workspace):
            self.repository.assert_revision(registry_path, revision)
            project = self._load(workspace)
            if handler_id not in project.handlers:
                raise ResourceNotFound(f"Handler '{handler_id}' does not exist.")
            usages = handler_usages(project, handler_id)
            if usages:
                raise ResourceInUse(
                    f"Handler '{handler_id}' is still referenced {len(usages)} time(s)."
                )
            before = registry_path.read_bytes()
            registry = self.repository.read_json(registry_path)
            registry["handlers"] = [
                value
                for value in registry.get("handlers", [])
                if not isinstance(value, dict) or value.get("id") != handler_id
            ]
            try:
                self.repository.atomic_write_json(registry_path, registry)
                self._load(workspace)
            except BaseException:
                self.repository.restore(registry_path, before)
                raise

    def detach_handler(
        self,
        project_id: str,
        handler_id: str,
        *,
        attachment: Mapping[str, Any],
        target_revision: str,
    ) -> dict[str, Any]:
        """Detach one typed trigger while preserving both binding and user source."""

        workspace = self.repository.workspace(project_id)
        with self.repository.lock(workspace):
            project = self._load(workspace)
            if handler_id not in project.handlers:
                raise ResourceNotFound(f"Handler '{handler_id}' does not exist.")
            path, payload = self._detachment_document(
                workspace, project, attachment, handler_id
            )
            self.repository.assert_revision(path, target_revision)
            before = path.read_bytes()
            try:
                self.repository.atomic_write_json(path, payload)
                candidate = self._load(workspace)
                errors = [
                    item
                    for item in validate_project(candidate, inspect_code=True)
                    if item.level == "error"
                ]
                if errors:
                    raise WorkspaceError(
                        "Handler detach would leave the project invalid: "
                        + "; ".join(item.message for item in errors)
                    )
            except BaseException:
                self.repository.restore(path, before)
                raise
        return self.get_handler(project_id, handler_id)

    # Validation ----------------------------------------------------------------------

    def validate(self, project_id: str) -> list[dict[str, Any]]:
        workspace = self.repository.workspace(project_id)
        _, diagnostics = load_and_validate_project(
            workspace.root, inspect_code=True
        )
        return [item.as_dict() for item in diagnostics]

    # Internal resource operations ----------------------------------------------------

    def _list_resources(self, project_id: str, kind: str) -> list[dict[str, Any]]:
        workspace = self.repository.workspace(project_id)
        project = self._load(workspace)
        values = getattr(project, kind)
        return self._catalog_summaries(workspace, values.values())

    def _get_resource(self, project_id: str, kind: str, entity_id: str) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        project = self._load(workspace)
        path = self._entity_path(workspace, project, kind, entity_id)
        return self.repository.detail(
            path, resource_root=workspace.resources, entity_id=entity_id
        )

    def _create_resource(
        self,
        project_id: str,
        kind: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._validate_resource_id(entity_id)
        workspace = self.repository.workspace(project_id)
        path = self.repository.safe_path(
            workspace.resources, Path(kind) / f"{entity_id}.json", suffix=".json"
        )
        normalized = self._normalize_entity(payload, entity_id)
        with self.repository.lock(workspace):
            project = self._load(workspace)
            if entity_id in getattr(project, kind):
                raise ResourceConflict(f"{kind[:-1].title()} '{entity_id}' already exists.")
            self.repository.assert_revision(path, None, creating=True)
            try:
                self.repository.atomic_write_json(path, normalized)
                self._load(workspace)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        return self._get_resource(project_id, kind, entity_id)

    def _save_resource(
        self,
        project_id: str,
        kind: str,
        entity_id: str,
        payload: dict[str, Any],
        revision: str,
    ) -> dict[str, Any]:
        workspace = self.repository.workspace(project_id)
        normalized = self._normalize_entity(payload, entity_id)
        with self.repository.lock(workspace):
            project = self._load(workspace)
            path = self._entity_path(workspace, project, kind, entity_id)
            self.repository.assert_revision(path, revision)
            before = path.read_bytes()
            try:
                self.repository.atomic_write_json(path, normalized)
                self._load(workspace)
            except BaseException:
                self.repository.restore(path, before)
                raise
        return self._get_resource(project_id, kind, entity_id)

    def _delete_resource(
        self, project_id: str, kind: str, entity_id: str, revision: str
    ) -> None:
        workspace = self.repository.workspace(project_id)
        with self.repository.lock(workspace):
            project = self._load(workspace)
            path = self._entity_path(workspace, project, kind, entity_id)
            self.repository.assert_revision(path, revision)
            usages = self._resource_usages(project, kind, entity_id, path)
            if usages:
                raise ResourceInUse(
                    f"Cannot delete '{entity_id}'; it is referenced {len(usages)} time(s)."
                )
            before = path.read_bytes()
            try:
                path.unlink()
                self._load(workspace)
            except BaseException:
                self.repository.restore(path, before)
                raise

    def _save_json_and_parse(
        self,
        workspace: Workspace,
        path: Path,
        payload: Mapping[str, Any],
        revision: str,
    ) -> None:
        with self.repository.lock(workspace):
            self.repository.assert_revision(path, revision)
            before = path.read_bytes()
            try:
                self.repository.atomic_write_json(path, payload)
                self._load(workspace)
            except BaseException:
                self.repository.restore(path, before)
                raise

    def _load(self, workspace: Workspace):
        try:
            return self.loader.load(workspace.root)
        except ProjectLoadError as error:
            raise WorkspaceError(str(error)) from error

    async def _user_store(
        self, project_id: str
    ) -> tuple[Workspace, str, SqliteStore]:
        workspace = self.repository.workspace(project_id)
        project = self._load(workspace)
        store = SqliteStore(workspace.root / "data" / "runtime.sqlite3")
        await store.initialize()
        return workspace, project.manifest.id, store

    @staticmethod
    def _user_detail(user: BotUser) -> dict[str, Any]:
        return {
            "telegram_id": str(user.user_id),
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
            "role": user.role,
            "status": "blocked" if user.blocked else "active",
            "note": user.note,
            "avatar_version": user.avatar_file_id,
        }

    @staticmethod
    def _normalize_entity(payload: dict[str, Any], entity_id: str) -> dict[str, Any]:
        supplied_id = payload.get("id")
        if supplied_id is not None and supplied_id != entity_id:
            raise WorkspaceError("Payload id must match the resource id.")
        normalized = dict(payload)
        normalized["schema_version"] = 3
        normalized["id"] = entity_id
        return normalized

    @staticmethod
    def _validate_resource_id(entity_id: str) -> None:
        if not _ID.fullmatch(entity_id):
            raise WorkspaceError(
                "Resource id must start with a letter and contain only letters, numbers, _, - or dot."
            )

    @staticmethod
    def _entity_path(workspace: Workspace, project, kind: str, entity_id: str) -> Path:
        if kind not in _RESOURCE_KINDS:
            raise WorkspaceError(f"Unsupported resource kind '{kind}'.")
        try:
            entity = getattr(project, kind)[entity_id]
        except KeyError as error:
            raise ResourceNotFound(f"{kind[:-1].title()} '{entity_id}' does not exist.") from error
        if not entity.source_path:
            raise WorkspaceError(f"{kind[:-1].title()} '{entity_id}' has no source path.")
        return WorkspaceRepository.safe_path(
            workspace.resources, entity.source_path, suffix=".json"
        )

    @staticmethod
    def _catalog_summaries(workspace: Workspace, entities) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for entity in sorted(entities, key=lambda item: item.id):
            path = WorkspaceRepository.safe_path(
                workspace.resources, entity.source_path, suffix=".json"
            )
            values.append(
                {
                    "id": entity.id,
                    "source_path": entity.source_path,
                    "revision": content_revision(path.read_bytes()),
                }
            )
        return values

    def _handler_summaries(self, workspace: Workspace, project) -> list[dict[str, Any]]:
        revision = content_revision((workspace.resources / "handlers.json").read_bytes())
        values: list[dict[str, Any]] = []
        for binding in sorted(project.handlers.values(), key=lambda item: item.id):
            usages = handler_usages(project, binding.id)
            values.append(
                {
                    **self._binding_payload(binding),
                    "revision": revision,
                    "inspection": self.inspector.inspect(workspace, binding, usages),
                    "usage_count": len(usages),
                }
            )
        return values

    @staticmethod
    def _binding_payload(binding) -> dict[str, Any]:
        return {
            "id": binding.id,
            "module": binding.module,
            "symbol": binding.symbol,
            "kind": binding.kind,
            "outcomes": list(binding.outcomes),
            **({"description": binding.description} if binding.description else {}),
        }

    def _attachment_document(
        self,
        workspace: Workspace,
        project,
        attachment: Mapping[str, Any],
        handler_id: str,
        routes: Mapping[str, Any],
    ) -> tuple[Path, dict[str, Any], str]:
        attachment_type = attachment.get("type")
        invocation = {"handler": handler_id, "outcomes": dict(routes)}
        action = {"type": "handler.invoke", "handler": handler_id, "outcomes": dict(routes)}

        if attachment_type == "view_button":
            view_id = self._attachment_string(attachment, "view_id")
            button_id = self._attachment_string(attachment, "button_id")
            path = self._entity_path(workspace, project, "views", view_id)
            payload = self.repository.read_json(path)
            matches = [
                button
                for row in payload.get("keyboard", [])
                if isinstance(row, list)
                for button in row
                if isinstance(button, dict) and button.get("id") == button_id
            ]
            if len(matches) != 1:
                raise WorkspaceError(
                    f"View '{view_id}' must contain exactly one button '{button_id}'."
                )
            matches[0]["action"] = action
            return path, payload, "button"

        if attachment_type in {
            "flow_event",
            "state_on_message",
            "state_on_enter",
            "flow_lifecycle",
        }:
            flow_id = self._attachment_string(attachment, "flow_id")
            path = self._entity_path(workspace, project, "flows", flow_id)
            payload = self.repository.read_json(path)
            if attachment_type == "flow_lifecycle":
                hook = self._attachment_string(attachment, "hook")
                if hook not in {"on_start", "on_complete", "on_cancel", "on_error"}:
                    raise WorkspaceError("Unknown flow lifecycle hook.")
                lifecycle = payload.setdefault("lifecycle", {})
                if not isinstance(lifecycle, dict):
                    raise WorkspaceError("Flow lifecycle must be an object.")
                lifecycle[hook] = invocation
                return path, payload, "lifecycle"

            state_id = self._attachment_string(attachment, "state_id")
            states = payload.get("states")
            state = states.get(state_id) if isinstance(states, dict) else None
            if not isinstance(state, dict):
                raise WorkspaceError(f"Flow '{flow_id}' has no state '{state_id}'.")
            if attachment_type == "flow_event":
                event_id = self._attachment_string(attachment, "event_id")
                events = state.setdefault("events", {})
                if not isinstance(events, dict):
                    raise WorkspaceError("State events must be an object.")
                events[event_id] = invocation
                return path, payload, "button"
            field = "on_message" if attachment_type == "state_on_message" else "on_enter"
            state[field] = invocation
            return path, payload, "message" if field == "on_message" else "lifecycle"

        if attachment_type == "command":
            command_name = self._attachment_string(attachment, "command").removeprefix("/")
            path = workspace.resources / "commands.json"
            payload = self.repository.read_json(path)
            matches = [
                command
                for command in payload.get("commands", [])
                if isinstance(command, dict)
                and str(command.get("name", "")).removeprefix("/") == command_name
            ]
            if len(matches) != 1:
                raise WorkspaceError(f"Command '/{command_name}' does not exist exactly once.")
            matches[0]["action"] = action
            return path, payload, "command"

        if attachment_type in {
            "global_message_fallback",
            "global_command_fallback",
        }:
            path = workspace.resources / "commands.json"
            payload = self.repository.read_json(path)
            field = (
                "message_fallback"
                if attachment_type == "global_message_fallback"
                else "command_fallback"
            )
            payload[field] = action
            expected = "message" if field == "message_fallback" else "command"
            return path, payload, expected

        if attachment_type == "schedule":
            schedule_id = self._attachment_string(attachment, "schedule_id")
            path = self._entity_path(workspace, project, "schedules", schedule_id)
            payload = self.repository.read_json(path)
            payload["handler"] = handler_id
            return path, payload, "task"

        raise WorkspaceError(f"Unsupported handler attachment type '{attachment_type}'.")

    def _detachment_document(
        self,
        workspace: Workspace,
        project,
        attachment: Mapping[str, Any],
        handler_id: str,
    ) -> tuple[Path, dict[str, Any]]:
        attachment_type = attachment.get("type")

        def require_invocation(value: Any) -> None:
            if not isinstance(value, dict) or value.get("handler") != handler_id:
                raise WorkspaceError(
                    f"Selected trigger is not attached to handler '{handler_id}'."
                )

        if attachment_type == "view_button":
            view_id = self._attachment_string(attachment, "view_id")
            button_id = self._attachment_string(attachment, "button_id")
            path = self._entity_path(workspace, project, "views", view_id)
            payload = self.repository.read_json(path)
            matches = [
                button
                for row in payload.get("keyboard", [])
                if isinstance(row, list)
                for button in row
                if isinstance(button, dict) and button.get("id") == button_id
            ]
            if len(matches) != 1:
                raise WorkspaceError(
                    f"View '{view_id}' must contain exactly one button '{button_id}'."
                )
            require_invocation(matches[0].get("action"))
            matches[0]["action"] = {"type": "noop"}
            return path, payload

        if attachment_type in {
            "flow_event",
            "state_on_message",
            "state_on_enter",
            "flow_lifecycle",
        }:
            flow_id = self._attachment_string(attachment, "flow_id")
            path = self._entity_path(workspace, project, "flows", flow_id)
            payload = self.repository.read_json(path)
            if attachment_type == "flow_lifecycle":
                hook = self._attachment_string(attachment, "hook")
                lifecycle = payload.get("lifecycle")
                value = lifecycle.get(hook) if isinstance(lifecycle, dict) else None
                require_invocation(value)
                lifecycle.pop(hook)
                return path, payload
            state_id = self._attachment_string(attachment, "state_id")
            states = payload.get("states")
            state = states.get(state_id) if isinstance(states, dict) else None
            if not isinstance(state, dict):
                raise WorkspaceError(f"Flow '{flow_id}' has no state '{state_id}'.")
            if attachment_type == "flow_event":
                event_id = self._attachment_string(attachment, "event_id")
                events = state.get("events")
                value = events.get(event_id) if isinstance(events, dict) else None
                require_invocation(value)
                events.pop(event_id)
                return path, payload
            field = "on_message" if attachment_type == "state_on_message" else "on_enter"
            require_invocation(state.get(field))
            state.pop(field)
            return path, payload

        if attachment_type == "command":
            command_name = self._attachment_string(attachment, "command").removeprefix("/")
            path = workspace.resources / "commands.json"
            payload = self.repository.read_json(path)
            matches = [
                command
                for command in payload.get("commands", [])
                if isinstance(command, dict)
                and str(command.get("name", "")).removeprefix("/") == command_name
            ]
            if len(matches) != 1:
                raise WorkspaceError(f"Command '/{command_name}' does not exist exactly once.")
            require_invocation(matches[0].get("action"))
            matches[0]["action"] = {"type": "noop"}
            return path, payload

        if attachment_type in {
            "global_message_fallback",
            "global_command_fallback",
        }:
            path = workspace.resources / "commands.json"
            payload = self.repository.read_json(path)
            field = (
                "message_fallback"
                if attachment_type == "global_message_fallback"
                else "command_fallback"
            )
            require_invocation(payload.get(field))
            payload.pop(field)
            return path, payload

        if attachment_type == "schedule":
            raise WorkspaceError(
                "A schedule requires a task handler; delete or rebind the schedule instead."
            )
        raise WorkspaceError(f"Unsupported handler attachment type '{attachment_type}'.")

    @staticmethod
    def _attachment_string(attachment: Mapping[str, Any], key: str) -> str:
        value = attachment.get(key)
        if not isinstance(value, str) or not value:
            raise WorkspaceError(f"Attachment field '{key}' is required.")
        return value

    def _ensure_handler_packages(self, workspace: Workspace, source_parent: Path) -> list[Path]:
        handlers_root = self.repository.safe_path(
            workspace.root,
            Path("src").joinpath(*workspace.package.split("."), "handlers"),
        )
        source_parent.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []
        current = handlers_root
        while True:
            initializer = current / "__init__.py"
            if self.repository.create_exclusive(initializer, ""):
                created.append(initializer)
            if current == source_parent:
                break
            relative = source_parent.relative_to(current)
            current = current / relative.parts[0]
        return created

    @staticmethod
    def _directory_identity(path: Path) -> tuple[int, int]:
        stat = path.stat(follow_symlinks=False)
        if path.is_symlink() or not path.is_dir():
            raise WorkspaceError("Generated project root is not a regular directory.")
        return stat.st_dev, stat.st_ino

    @staticmethod
    def _remove_created_directory(path: Path, identity: tuple[int, int]) -> None:
        try:
            stat = path.stat(follow_symlinks=False)
        except OSError:
            return
        if path.is_symlink() or not path.is_dir():
            return
        if (stat.st_dev, stat.st_ino) != identity:
            return
        shutil.rmtree(path, ignore_errors=True)

    @staticmethod
    def _resource_usages(project, kind: str, entity_id: str, source_path: Path) -> list[str]:
        usages: list[str] = []
        excluded_source = source_path.relative_to(project.resources).as_posix()

        def action(value, source: str, field: str) -> None:
            if source == excluded_source:
                return
            if kind == "views" and (
                (value.type == "view.render" and value.target == entity_id)
                or value.view == entity_id
            ):
                usages.append(f"{source}:{field}")
            if kind == "flows" and value.type == "flow.start" and value.target == entity_id:
                usages.append(f"{source}:{field}")
            for outcome, nested in value.outcomes.items():
                action(nested, source, f"{field}.outcomes.{outcome}")

        if kind == "views" and project.manifest.entry_view == entity_id:
            usages.append("bot.json:entry_view")
        if kind == "flows" and project.manifest.start.flow == entity_id:
            usages.append("bot.json:start.flow")
        if kind == "views":
            for flow in project.flows.values():
                for state in flow.states.values():
                    if state.view == entity_id:
                        usages.append(f"{flow.source_path}:states.{state.id}.view")
        for view in project.views.values():
            for row_index, row in enumerate(view.keyboard):
                for index, button in enumerate(row):
                    action(button.action, view.source_path or "", f"keyboard.{row_index}.{index}.action")
        for command in project.commands.commands:
            action(command.action, "commands.json", f"commands.{command.name}.action")
        if project.commands.message_fallback:
            action(project.commands.message_fallback, "commands.json", "message_fallback")
        if project.commands.command_fallback:
            action(project.commands.command_fallback, "commands.json", "command_fallback")
        for flow in project.flows.values():
            invocations = [
                flow.lifecycle.on_start,
                flow.lifecycle.on_complete,
                flow.lifecycle.on_cancel,
                flow.lifecycle.on_error,
            ]
            for state in flow.states.values():
                invocations.extend([state.on_enter, state.on_message, *state.events.values()])
            for invocation in (value for value in invocations if value is not None):
                for outcome, route in invocation.outcomes.items():
                    action(route, flow.source_path or "", f"outcomes.{outcome}")
        return usages

    @staticmethod
    def _replace_view_reference(value: Any, old_id: str, new_id: str) -> None:
        if isinstance(value, list):
            for item in value:
                ProjectService._replace_view_reference(item, old_id, new_id)
            return
        if not isinstance(value, dict):
            return
        if value.get("view") == old_id:
            value["view"] = new_id
        if value.get("type") == "view.render" and value.get("target") == old_id:
            value["target"] = new_id
        for item in value.values():
            ProjectService._replace_view_reference(item, old_id, new_id)

    @staticmethod
    def _replace_flow_reference(value: Any, old_id: str, new_id: str) -> None:
        if isinstance(value, list):
            for item in value:
                ProjectService._replace_flow_reference(item, old_id, new_id)
            return
        if not isinstance(value, dict):
            return
        if value.get("type") == "flow.start" and value.get("target") == old_id:
            value["target"] = new_id
        for item in value.values():
            ProjectService._replace_flow_reference(item, old_id, new_id)

    @staticmethod
    def _replace_handler_reference(value: Any, old_id: str, new_id: str) -> None:
        if isinstance(value, list):
            for item in value:
                ProjectService._replace_handler_reference(item, old_id, new_id)
            return
        if not isinstance(value, dict):
            return
        if value.get("handler") == old_id:
            value["handler"] = new_id
        for item in value.values():
            ProjectService._replace_handler_reference(item, old_id, new_id)


__all__ = [
    "ProjectService",
    "ResourceConflict",
    "ResourceInUse",
    "ResourceNotFound",
    "RevisionConflict",
    "WorkspaceError",
    "WorkspaceNotFound",
]
