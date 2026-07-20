from __future__ import annotations

import hashlib
import json
import keyword
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from tg_bot_core.project import ProjectLoadError, ProjectLoader


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


class ResourceConflict(WorkspaceError):
    status_code = 409
    code = "resource_conflict"


class ResourceInUse(ResourceConflict):
    code = "resource_in_use"


@dataclass(frozen=True, slots=True)
class Workspace:
    id: str
    root: Path
    resources: Path
    package: str


def content_revision(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class WorkspaceRepository:
    """Opened project roots plus safe, revision-aware filesystem primitives."""

    def __init__(self, loader: ProjectLoader | None = None) -> None:
        self.loader = loader or ProjectLoader()
        self._workspaces: dict[str, Workspace] = {}
        self._ids_by_root: dict[Path, str] = {}
        self._locks_by_root: dict[Path, threading.RLock] = {}
        self._registry_lock = threading.RLock()

    def open(self, root_path: str | Path) -> Workspace:
        try:
            project = self.loader.load(Path(root_path).expanduser())
        except ProjectLoadError as error:
            raise WorkspaceError(str(error)) from error
        root = project.root.resolve()
        package = self._project_package(project.resources)
        package_root = self.safe_path(
            root, Path("src").joinpath(*package.split("."))
        )
        if not package_root.is_dir():
            raise WorkspaceError(f"Project package directory does not exist: src/{package}")
        with self._registry_lock:
            existing_id = self._ids_by_root.get(root)
            if existing_id is not None:
                return self._workspaces[existing_id]
            workspace = Workspace(str(uuid4()), root, project.resources.resolve(), package)
            self._workspaces[workspace.id] = workspace
            self._ids_by_root[root] = workspace.id
            self._locks_by_root[root] = threading.RLock()
            return workspace

    def workspace(self, project_id: str) -> Workspace:
        try:
            return self._workspaces[project_id]
        except KeyError as error:
            raise WorkspaceNotFound("Project is not open.") from error

    def forget(self, project_id: str) -> None:
        """Forget a just-opened workspace when project creation rolls back."""

        with self._registry_lock:
            workspace = self._workspaces.pop(project_id, None)
            if workspace is None:
                return
            if self._ids_by_root.get(workspace.root) == project_id:
                self._ids_by_root.pop(workspace.root, None)
            self._locks_by_root.pop(workspace.root, None)

    def lock(self, workspace: Workspace) -> threading.RLock:
        return self._locks_by_root[workspace.root]

    @staticmethod
    def safe_path(base: Path, relative: str | Path, *, suffix: str | None = None) -> Path:
        raw = Path(relative)
        if not str(relative) or raw.is_absolute() or ".." in raw.parts:
            raise WorkspaceError("Path must be a non-empty relative path without '..'.")
        resolved_base = base.resolve()
        target = (resolved_base / raw).resolve(strict=False)
        if not target.is_relative_to(resolved_base):
            raise WorkspaceError("Path must stay inside the project.")
        if suffix is not None and target.suffix.lower() != suffix.lower():
            raise WorkspaceError(f"Path must end with {suffix}.")
        return target

    @staticmethod
    def read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkspaceError(f"Invalid JSON resource '{path}': {error}") from error
        if not isinstance(value, dict):
            raise WorkspaceError(f"JSON resource must be an object: {path}")
        return value

    @staticmethod
    def json_bytes(data: Mapping[str, Any]) -> bytes:
        return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    @staticmethod
    def read_revision(path: Path) -> str:
        if not path.is_file():
            raise ResourceNotFound(f"Resource does not exist: {path.name}")
        return content_revision(path.read_bytes())

    @staticmethod
    def assert_revision(path: Path, expected: str | None, *, creating: bool = False) -> None:
        if path.exists():
            if creating:
                raise ResourceConflict(f"Resource already exists: {path.name}")
            if expected is None or content_revision(path.read_bytes()) != expected:
                raise RevisionConflict("The resource changed outside Studio. Reload it before saving.")
        elif not creating:
            raise ResourceNotFound(f"Resource does not exist: {path.name}")
        elif expected is not None:
            raise RevisionConflict("The resource was created outside Studio.")

    @staticmethod
    def atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    @classmethod
    def atomic_write_json(cls, path: Path, data: Mapping[str, Any]) -> None:
        cls.atomic_write(path, cls.json_bytes(data))

    @staticmethod
    def create_exclusive(path: Path, content: str) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            return True
        except FileExistsError:
            return False

    @classmethod
    def restore(cls, path: Path, previous: bytes | None) -> None:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            cls.atomic_write(path, previous)

    @staticmethod
    def detail(path: Path, *, resource_root: Path, entity_id: str | None = None) -> dict[str, Any]:
        raw = path.read_bytes()
        payload = WorkspaceRepository.read_json(path)
        return {
            **({"id": entity_id} if entity_id is not None else {}),
            "source_path": path.relative_to(resource_root).as_posix(),
            "revision": content_revision(raw),
            "payload": payload,
        }

    @staticmethod
    def _project_package(resources: Path) -> str:
        manifest = WorkspaceRepository.read_json(resources / "bot.json")
        package = manifest.get("package")
        if (
            not isinstance(package, str)
            or not package
            or any(
                not part.isidentifier() or keyword.iskeyword(part)
                for part in package.split(".")
            )
        ):
            raise WorkspaceError("resources/bot.json must declare a valid Python 'package'.")
        return package
