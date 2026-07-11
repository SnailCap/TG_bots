from __future__ import annotations

from uuid import uuid4

from app.domain.enums import NodeType, TransitionKind
from app.domain.flow import Flow, Node, NodePosition, Transition
from app.domain.ports.events import EventPublisher
from app.domain.ports.projects import ProjectRepository
from app.domain.runtime import RuntimeEvent
from app.errors import ConflictError

from .projects import ProjectApplicationService


class FlowApplicationService:
    def __init__(
        self,
        projects: ProjectApplicationService,
        repository: ProjectRepository,
        events: EventPublisher | None = None,
    ) -> None:
        self._projects = projects
        self._repository = repository
        self._events = events

    def list(self, project_id: str) -> tuple[Flow, ...]:
        return tuple(self._repository.list_flows(self._projects.root(project_id)))

    def get(self, project_id: str, flow_id: str) -> Flow:
        return self._repository.load_flow(self._projects.root(project_id), flow_id)

    async def create(self, project_id: str, *, name: str) -> Flow:
        start_id = str(uuid4())
        end_id = str(uuid4())
        flow = Flow(
            id=str(uuid4()),
            name=name.strip(),
            start_node_id=start_id,
            nodes=(
                Node(
                    id=start_id,
                    type=NodeType.START,
                    name="Start",
                    position=NodePosition(x=80, y=120),
                ),
                Node(
                    id=end_id,
                    type=NodeType.END,
                    name="End",
                    position=NodePosition(x=380, y=120),
                ),
            ),
            transitions=(
                Transition(
                    id=str(uuid4()),
                    source_node_id=start_id,
                    target_node_id=end_id,
                    kind=TransitionKind.AUTOMATIC,
                ),
            ),
        )
        if not flow.name:
            raise ValueError("Flow name must not be empty")
        self._repository.save_flow(self._projects.root(project_id), flow)
        await self._publish(project_id, "flow.created", f"Flow {flow.name!r} created", flow.id)
        return flow

    async def save(self, project_id: str, flow_id: str, flow: Flow) -> Flow:
        if flow.id != flow_id:
            raise ConflictError("Flow id in URL and payload do not match")
        self._repository.save_flow(self._projects.root(project_id), flow)
        await self._publish(project_id, "flow.saved", f"Flow {flow.name!r} saved", flow.id)
        return flow

    async def delete(self, project_id: str, flow_id: str) -> None:
        opened = self._projects.get(project_id)
        if opened.project.configuration.start_flow_id == flow_id:
            raise ConflictError("Cannot delete the configured start flow")
        self._repository.delete_flow(opened.path, flow_id)
        await self._publish(project_id, "flow.deleted", "Flow deleted", flow_id)

    async def _publish(
        self,
        project_id: str,
        category: str,
        message: str,
        flow_id: str,
    ) -> None:
        if self._events is not None:
            await self._events.publish(
                RuntimeEvent(
                    project_id=project_id,
                    category=category,
                    message=message,
                    entity_type="flow",
                    entity_id=flow_id,
                )
            )

