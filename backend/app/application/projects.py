from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from app.domain.ports.events import EventPublisher
from app.domain.ports.projects import ProjectRepository, RecentProjectsRepository
from app.domain.project import BotProject, ProjectTreeEntry, RecentProject
from app.domain.runtime import RuntimeEvent
from app.errors import ProjectNotFoundError


@dataclass(frozen=True, slots=True)
class OpenedProject:
    project: BotProject
    path: Path


class ProjectApplicationService:
    def __init__(
        self,
        repository: ProjectRepository,
        recent_repository: RecentProjectsRepository,
        events: EventPublisher | None = None,
    ) -> None:
        self._repository = repository
        self._recent = recent_repository
        self._events = events
        self._opened: dict[str, OpenedProject] = {}

    async def create(self, *, directory: str, name: str) -> OpenedProject:
        root = Path(directory).expanduser().resolve(strict=False)
        project = BotProject.create(name)
        self._repository.create(root, project)
        opened = self._remember(project, root)
        await self._publish(project.id, "project.created", f"Project {project.name!r} created")
        return opened

    async def open(self, path: str) -> OpenedProject:
        root = Path(path).expanduser().resolve(strict=False)
        project = self._repository.open(root)
        opened = self._remember(project, root)
        await self._publish(project.id, "project.opened", f"Project {project.name!r} opened")
        return opened

    def get(self, project_id: str) -> OpenedProject:
        opened = self._opened.get(project_id)
        if opened is None:
            recent = next(
                (item for item in self._recent.list() if item.project_id == project_id),
                None,
            )
            if recent is not None and recent.exists:
                root = Path(recent.path).expanduser().resolve(strict=False)
                project = self._repository.open(root)
                if project.id == project_id:
                    opened = self._remember(project, root)
        if opened is None:
            raise ProjectNotFoundError(
                f"Project is not open: {project_id}",
                details={"project_id": project_id},
            )
        return opened

    def recent(self) -> tuple[RecentProject, ...]:
        return tuple(self._recent.list())

    def tree(self, project_id: str) -> tuple[ProjectTreeEntry, ...]:
        opened = self.get(project_id)
        return tuple(self._repository.tree(opened.path))

    async def rename(self, project_id: str, name: str) -> OpenedProject:
        normalized = name.strip()
        if not normalized:
            raise ValueError("Project name must not be empty")
        opened = self.get(project_id)
        project = replace(
            opened.project,
            name=normalized,
            updated_at=datetime.now(UTC),
        )
        self._repository.save_project(opened.path, project)
        updated = self._remember(project, opened.path)
        await self._publish(project_id, "project.updated", "Project settings updated")
        return updated

    async def save_project(self, project_id: str, project: BotProject) -> OpenedProject:
        opened = self.get(project_id)
        if project.id != project_id:
            raise ValueError("Cannot replace a project with a different id")
        updated_project = replace(project, updated_at=datetime.now(UTC))
        self._repository.save_project(opened.path, updated_project)
        return self._remember(updated_project, opened.path)

    def root(self, project_id: str) -> Path:
        return self.get(project_id).path

    def _remember(self, project: BotProject, root: Path) -> OpenedProject:
        opened = OpenedProject(project=project, path=root)
        self._opened[project.id] = opened
        self._recent.add(
            RecentProject(
                project_id=project.id,
                name=project.name,
                path=str(root),
            )
        )
        return opened

    async def _publish(self, project_id: str, category: str, message: str) -> None:
        if self._events is not None:
            await self._events.publish(
                RuntimeEvent(project_id=project_id, category=category, message=message)
            )
