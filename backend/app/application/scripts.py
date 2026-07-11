from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import NodeType
from app.domain.ports.events import EventPublisher
from app.domain.ports.projects import ProjectRepository
from app.domain.runtime import RuntimeEvent
from app.errors import ConflictError, ScriptNotFoundError
from app.infrastructure.project_storage.paths import normalize_script_path
from app.infrastructure.scripts import ScriptDiscovery, ScriptDiscoveryResult

from .projects import ProjectApplicationService


@dataclass(frozen=True, slots=True)
class ScriptSearchMatch:
    path: str
    line: int
    column: int
    preview: str


@dataclass(frozen=True, slots=True)
class ActionUsage:
    action_name: str
    flow_id: str
    flow_name: str
    node_id: str
    node_name: str


class ScriptApplicationService:
    def __init__(
        self,
        projects: ProjectApplicationService,
        repository: ProjectRepository,
        discovery: ScriptDiscovery,
        events: EventPublisher | None = None,
    ) -> None:
        self._projects = projects
        self._repository = repository
        self._discovery = discovery
        self._events = events

    def list(self, project_id: str) -> tuple[str, ...]:
        return tuple(
            self._canonical_path(path)
            for path in self._repository.list_scripts(self._projects.root(project_id))
        )

    def read(self, project_id: str, path: str) -> str:
        return self._repository.read_script(
            self._projects.root(project_id), self._internal_path(path)
        )

    async def create(self, project_id: str, path: str, content: str = "") -> str:
        normalized = self._canonical_path(self._internal_path(path))
        if normalized in self.list(project_id):
            raise ConflictError(f"Script already exists: {normalized}")
        self._repository.save_script(
            self._projects.root(project_id), self._internal_path(normalized), content
        )
        await self._publish(project_id, "script.created", "Script created", normalized)
        return normalized

    async def save(self, project_id: str, path: str, content: str) -> str:
        normalized = self._canonical_path(self._internal_path(path))
        if normalized not in self.list(project_id):
            raise ScriptNotFoundError(f"Script not found: {normalized}")
        self._repository.save_script(
            self._projects.root(project_id), self._internal_path(normalized), content
        )
        await self._publish(project_id, "script.saved", "Script saved", normalized)
        return normalized

    async def rename(self, project_id: str, path: str, new_path: str) -> str:
        normalized = self._canonical_path(self._internal_path(path))
        normalized_new = self._canonical_path(self._internal_path(new_path))
        self._repository.rename_script(
            self._projects.root(project_id),
            self._internal_path(normalized),
            self._internal_path(normalized_new),
        )
        await self._publish(project_id, "script.renamed", "Script renamed", normalized_new)
        return normalized_new

    async def delete(self, project_id: str, path: str) -> None:
        normalized = self._canonical_path(self._internal_path(path))
        self._repository.delete_script(
            self._projects.root(project_id), self._internal_path(normalized)
        )
        await self._publish(project_id, "script.deleted", "Script deleted", normalized)

    def search(
        self,
        project_id: str,
        query: str,
        *,
        limit: int = 200,
    ) -> tuple[ScriptSearchMatch, ...]:
        needle = query.casefold()
        if not needle:
            return ()
        matches: list[ScriptSearchMatch] = []
        for path in self.list(project_id):
            content = self.read(project_id, path)
            for line_number, line in enumerate(content.splitlines(), start=1):
                column = line.casefold().find(needle)
                if column >= 0:
                    matches.append(
                        ScriptSearchMatch(
                            path=path,
                            line=line_number,
                            column=column + 1,
                            preview=line.strip()[:300],
                        )
                    )
                    if len(matches) >= min(max(1, limit), 1_000):
                        return tuple(matches)
        return tuple(matches)

    def actions(
        self,
        project_id: str,
        *,
        validate_imports: bool = True,
    ) -> ScriptDiscoveryResult:
        return self._discovery.discover(
            self._projects.root(project_id), validate_imports=validate_imports
        )

    def validate_source(
        self,
        project_id: str,
        path: str,
        content: str,
    ) -> ScriptDiscoveryResult:
        self._projects.get(project_id)
        normalized = self._canonical_path(self._internal_path(path))
        return self._discovery.discover_source(normalized, content)

    def usages(self, project_id: str, action_name: str) -> tuple[ActionUsage, ...]:
        result: list[ActionUsage] = []
        for flow in self._repository.list_flows(self._projects.root(project_id)):
            for node in flow.nodes:
                if node.type != NodeType.ACTION:
                    continue
                configured = node.config.get("action_name", node.config.get("action"))
                if configured == action_name:
                    result.append(
                        ActionUsage(
                            action_name=action_name,
                            flow_id=flow.id,
                            flow_name=flow.name,
                            node_id=node.id,
                            node_name=node.name,
                        )
                    )
        return tuple(result)

    @staticmethod
    def _internal_path(path: str) -> str:
        normalized = path.strip().replace("\\", "/")
        if normalized.startswith("scripts/"):
            normalized = normalized.removeprefix("scripts/")
        return normalize_script_path(normalized)

    @staticmethod
    def _canonical_path(path: str) -> str:
        normalized = normalize_script_path(path)
        return f"scripts/{normalized}"

    async def _publish(
        self,
        project_id: str,
        category: str,
        message: str,
        path: str,
    ) -> None:
        if self._events is not None:
            await self._events.publish(
                RuntimeEvent(
                    project_id=project_id,
                    category=category,
                    message=message,
                    entity_type="script",
                    entity_id=path,
                )
            )
