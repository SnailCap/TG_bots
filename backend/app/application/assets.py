from __future__ import annotations

from app.domain.ports.events import EventPublisher
from app.domain.ports.projects import ProjectRepository
from app.domain.runtime import RuntimeEvent
from app.errors import ConflictError
from app.infrastructure.project_storage.paths import normalize_asset_path

from .projects import ProjectApplicationService


class AssetApplicationService:
    def __init__(
        self,
        projects: ProjectApplicationService,
        repository: ProjectRepository,
        events: EventPublisher | None = None,
    ) -> None:
        self._projects = projects
        self._repository = repository
        self._events = events

    def list(self, project_id: str) -> tuple[str, ...]:
        return tuple(self._repository.list_assets(self._projects.root(project_id)))

    def read(self, project_id: str, path: str) -> bytes:
        return self._repository.read_asset(self._projects.root(project_id), path)

    async def create(self, project_id: str, path: str, content: bytes) -> str:
        normalized = normalize_asset_path(path)
        if normalized in self.list(project_id):
            raise ConflictError(f"Asset already exists: {normalized}")
        self._repository.save_asset(self._projects.root(project_id), normalized, content)
        await self._publish(project_id, "asset.created", normalized)
        return normalized

    async def save(self, project_id: str, path: str, content: bytes) -> str:
        normalized = normalize_asset_path(path)
        self._repository.save_asset(self._projects.root(project_id), normalized, content)
        await self._publish(project_id, "asset.saved", normalized)
        return normalized

    async def rename(self, project_id: str, path: str, new_path: str) -> str:
        normalized = normalize_asset_path(path)
        normalized_new = normalize_asset_path(new_path)
        self._repository.rename_asset(
            self._projects.root(project_id), normalized, normalized_new
        )
        await self._publish(project_id, "asset.renamed", normalized_new)
        return normalized_new

    async def delete(self, project_id: str, path: str) -> None:
        normalized = normalize_asset_path(path)
        self._repository.delete_asset(self._projects.root(project_id), normalized)
        await self._publish(project_id, "asset.deleted", normalized)

    async def _publish(self, project_id: str, category: str, path: str) -> None:
        if self._events is not None:
            await self._events.publish(
                RuntimeEvent(
                    project_id=project_id,
                    category=category,
                    message=category.replace(".", " ").title(),
                    entity_type="asset",
                    entity_id=path,
                )
            )

