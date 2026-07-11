from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.domain.ports.events import EventPublisher
from app.domain.ports.projects import ProjectRepository
from app.domain.ports.sessions import RuntimeStorage, SessionRepository
from app.domain.project import BotProject

from .actions import ProjectActionInvoker, ProjectActionLoader
from .events import RuntimeEventSink
from .executor import GraphExecutor
from .service import RuntimeService
from .transport import TelegramPort
from .validation import RuntimeProjectValidator


@dataclass(frozen=True, slots=True)
class RuntimeRepositories:
    sessions: SessionRepository
    storage: RuntimeStorage


TelegramFactory = Callable[[str], TelegramPort]
RepositoryFactory = Callable[[Path], RuntimeRepositories]


class StandardRuntimeFactory:
    """Composition seam used by the API container and later by a worker process."""

    def __init__(
        self,
        *,
        projects: ProjectRepository,
        telegram_factory: TelegramFactory,
        repository_factory: RepositoryFactory,
        publisher: EventPublisher | None = None,
        services: Any = None,
        action_loader: ProjectActionLoader | None = None,
        max_automatic_steps: int = 64,
    ) -> None:
        self._projects = projects
        self._telegram_factory = telegram_factory
        self._repository_factory = repository_factory
        self._publisher = publisher
        self._services = services
        self._actions = action_loader or ProjectActionLoader()
        self._max_automatic_steps = max_automatic_steps

    def __call__(
        self,
        project: BotProject,
        project_root: Path,
        token: str,
    ) -> RuntimeService:
        repositories = self._repository_factory(project_root)
        telegram = self._telegram_factory(token)
        events = RuntimeEventSink(
            project_id=project.id,
            publisher=self._publisher,
            storage=repositories.storage,
        )
        actions = ProjectActionInvoker(
            loader=self._actions,
            telegram=telegram,
            event_sink=events,
            storage=repositories.storage,
            services=self._services,
        )
        validator = RuntimeProjectValidator(
            projects=self._projects,
            action_loader=self._actions,
        )
        executor = GraphExecutor(
            project=project,
            project_root=project_root,
            projects=self._projects,
            sessions=repositories.sessions,
            telegram=telegram,
            actions=actions,
            events=events,
            max_automatic_steps=self._max_automatic_steps,
        )
        return RuntimeService(
            project=project,
            project_root=project_root,
            token=token,
            telegram=telegram,
            executor=executor,
            validator=validator,
            events=events,
        )

