from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Sequence

from app.domain.flow import Flow
from app.domain.project import BotProject, ProjectTreeEntry
from app.errors import (
    AssetNotFoundError,
    ConflictError,
    FlowNotFoundError,
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    ScriptNotFoundError,
)

from .codecs import (
    dump_json,
    flow_from_dict,
    flow_to_dict,
    load_json,
    project_from_dict,
    project_to_dict,
)
from .paths import (
    atomic_write_text,
    normalize_asset_path,
    normalize_script_path,
    require_safe_identifier,
    safe_child,
)


class FilesystemProjectRepository:
    BOT_FILE = "bot.json"
    PROJECT_DIRS = ("flows", "scripts", "assets", ".botstudio")

    def create(self, root: Path, project: BotProject) -> BotProject:
        project_root = root.expanduser().resolve(strict=False)
        if project_root.exists():
            if not project_root.is_dir():
                raise ProjectAlreadyExistsError(f"Project path is not a directory: {project_root}")
            if any(project_root.iterdir()):
                raise ProjectAlreadyExistsError(
                    f"Project directory is not empty: {project_root}"
                )
        else:
            project_root.mkdir(parents=True, exist_ok=False)

        for directory in self.PROJECT_DIRS:
            safe_child(project_root, directory).mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            safe_child(project_root, ".botstudio", ".gitignore"),
            "*\n!.gitignore\n",
        )
        self.save_project(project_root, project)
        return project

    def open(self, root: Path) -> BotProject:
        project_root = self._require_project(root)
        bot_file = safe_child(project_root, self.BOT_FILE)
        raw = load_json(bot_file.read_text(encoding="utf-8"), source=str(bot_file))
        return project_from_dict(raw)

    def save_project(self, root: Path, project: BotProject) -> None:
        project_root = root.expanduser().resolve(strict=False)
        if not project_root.exists() or not project_root.is_dir():
            raise ProjectNotFoundError(f"Project directory does not exist: {project_root}")
        bot_file = safe_child(project_root, self.BOT_FILE)
        atomic_write_text(bot_file, dump_json(project_to_dict(project)))

    def list_flows(self, root: Path) -> Sequence[Flow]:
        project_root = self._require_project(root)
        flows_root = safe_child(project_root, "flows")
        flows: list[Flow] = []
        for path in sorted(flows_root.glob("*.flow.json")):
            raw = load_json(path.read_text(encoding="utf-8"), source=str(path))
            flows.append(flow_from_dict(raw))
        return tuple(flows)

    def load_flow(self, root: Path, flow_id: str) -> Flow:
        path = self._flow_path(self._require_project(root), flow_id)
        if not path.is_file():
            raise FlowNotFoundError(f"Flow not found: {flow_id}")
        return flow_from_dict(load_json(path.read_text(encoding="utf-8"), source=str(path)))

    def save_flow(self, root: Path, flow: Flow) -> None:
        project_root = self._require_project(root)
        path = self._flow_path(project_root, flow.id)
        atomic_write_text(path, dump_json(flow_to_dict(flow)))

    def delete_flow(self, root: Path, flow_id: str) -> None:
        path = self._flow_path(self._require_project(root), flow_id)
        if not path.is_file():
            raise FlowNotFoundError(f"Flow not found: {flow_id}")
        path.unlink()

    def list_scripts(self, root: Path) -> Sequence[str]:
        scripts_root = safe_child(self._require_project(root), "scripts")
        result: list[str] = []
        for path in scripts_root.rglob("*.py"):
            if path.is_file() and not path.is_symlink():
                result.append(path.relative_to(scripts_root).as_posix())
        return tuple(sorted(result))

    def read_script(self, root: Path, relative_path: str) -> str:
        path = self._script_path(self._require_project(root), relative_path)
        if not path.is_file():
            raise ScriptNotFoundError(f"Script not found: {relative_path}")
        return path.read_text(encoding="utf-8")

    def save_script(self, root: Path, relative_path: str, content: str) -> None:
        path = self._script_path(self._require_project(root), relative_path)
        atomic_write_text(path, content)

    def rename_script(self, root: Path, relative_path: str, new_path: str) -> None:
        project_root = self._require_project(root)
        source = self._script_path(project_root, relative_path)
        destination = self._script_path(project_root, new_path)
        if not source.is_file():
            raise ScriptNotFoundError(f"Script not found: {relative_path}")
        if destination.exists():
            raise ConflictError(f"Destination script already exists: {new_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        self._remove_empty_parents(source.parent, safe_child(project_root, "scripts"))

    def delete_script(self, root: Path, relative_path: str) -> None:
        project_root = self._require_project(root)
        path = self._script_path(project_root, relative_path)
        if not path.is_file():
            raise ScriptNotFoundError(f"Script not found: {relative_path}")
        path.unlink()
        self._remove_empty_parents(path.parent, safe_child(project_root, "scripts"))

    def list_assets(self, root: Path) -> Sequence[str]:
        assets_root = safe_child(self._require_project(root), "assets")
        result = [
            path.relative_to(assets_root).as_posix()
            for path in assets_root.rglob("*")
            if path.is_file() and not path.is_symlink()
        ]
        return tuple(sorted(result))

    def read_asset(self, root: Path, relative_path: str) -> bytes:
        path = self._asset_path(self._require_project(root), relative_path)
        if not path.is_file():
            raise AssetNotFoundError(f"Asset not found: {relative_path}")
        return path.read_bytes()

    def save_asset(self, root: Path, relative_path: str, content: bytes) -> None:
        path = self._asset_path(self._require_project(root), relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def rename_asset(self, root: Path, relative_path: str, new_path: str) -> None:
        project_root = self._require_project(root)
        source = self._asset_path(project_root, relative_path)
        destination = self._asset_path(project_root, new_path)
        if not source.is_file():
            raise AssetNotFoundError(f"Asset not found: {relative_path}")
        if destination.exists():
            raise ConflictError(f"Destination asset already exists: {new_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        self._remove_empty_parents(source.parent, safe_child(project_root, "assets"))

    def delete_asset(self, root: Path, relative_path: str) -> None:
        project_root = self._require_project(root)
        path = self._asset_path(project_root, relative_path)
        if not path.is_file():
            raise AssetNotFoundError(f"Asset not found: {relative_path}")
        path.unlink()
        self._remove_empty_parents(path.parent, safe_child(project_root, "assets"))

    def tree(self, root: Path) -> Sequence[ProjectTreeEntry]:
        project_root = self._require_project(root)
        entries = [
            self._tree_directory(
                project_root, "flows", display_name="Flows", leaf_kind="flow"
            ),
            self._tree_directory(
                project_root, "scripts", display_name="Scripts", leaf_kind="script"
            ),
            self._tree_directory(
                project_root, "assets", display_name="Assets", leaf_kind="asset"
            ),
            ProjectTreeEntry(
                name="Settings",
                path=self.BOT_FILE,
                kind="settings",
                id=f"settings:{self.BOT_FILE}",
            ),
        ]
        return tuple(entries)

    def _require_project(self, root: Path) -> Path:
        project_root = root.expanduser().resolve(strict=False)
        bot_file = safe_child(project_root, self.BOT_FILE)
        if not project_root.is_dir() or not bot_file.is_file():
            raise ProjectNotFoundError(f"No Studio project at: {project_root}")
        return project_root

    @staticmethod
    def _flow_path(project_root: Path, flow_id: str) -> Path:
        safe_id = require_safe_identifier(flow_id, label="flow id")
        return safe_child(project_root, "flows", f"{safe_id}.flow.json")

    @staticmethod
    def _script_path(project_root: Path, relative_path: str) -> Path:
        normalized = normalize_script_path(relative_path)
        scripts_root = safe_child(project_root, "scripts")
        return safe_child(scripts_root, *normalized.split("/"))

    @staticmethod
    def _asset_path(project_root: Path, relative_path: str) -> Path:
        normalized = normalize_asset_path(relative_path)
        assets_root = safe_child(project_root, "assets")
        return safe_child(assets_root, *normalized.split("/"))

    def _tree_directory(
        self,
        project_root: Path,
        relative_path: str,
        *,
        display_name: str,
        leaf_kind: str,
    ) -> ProjectTreeEntry:
        directory = safe_child(project_root, relative_path)
        directory.mkdir(parents=True, exist_ok=True)
        children = tuple(self._tree_children(project_root, directory, leaf_kind=leaf_kind))
        return ProjectTreeEntry(
            name=display_name,
            path=relative_path,
            kind="directory",
            id=f"directory:{relative_path}",
            children=children,
        )

    def _tree_children(
        self,
        project_root: Path,
        directory: Path,
        *,
        leaf_kind: str,
    ) -> Iterable[ProjectTreeEntry]:
        for path in sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            if path.is_symlink():
                continue
            relative = path.relative_to(project_root).as_posix()
            if path.is_dir():
                yield ProjectTreeEntry(
                    name=path.name,
                    path=relative,
                    kind="directory",
                    id=f"directory:{relative}",
                    children=tuple(
                        self._tree_children(project_root, path, leaf_kind=leaf_kind)
                    ),
                )
            elif path.is_file():
                display_name = path.name
                if leaf_kind == "flow" and path.name.endswith(".flow.json"):
                    entry_id = path.name.removesuffix(".flow.json")
                    try:
                        raw = load_json(
                            path.read_text(encoding="utf-8"),
                            source=str(path),
                        )
                        display_name = flow_from_dict(raw).name
                    except Exception:
                        # Keep an invalid flow visible in Explorer so validation
                        # and manual recovery remain possible.
                        pass
                else:
                    entry_id = relative
                yield ProjectTreeEntry(
                    name=display_name,
                    path=relative,
                    kind=leaf_kind,
                    id=entry_id,
                    size=path.stat().st_size,
                )

    @staticmethod
    def _remove_empty_parents(directory: Path, stop: Path) -> None:
        current = directory
        while current != stop:
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent
