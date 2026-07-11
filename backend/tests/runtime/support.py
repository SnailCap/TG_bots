from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.domain.flow import Flow
from app.domain.project import BotConfiguration, BotIdentity, BotProject
from app.infrastructure.events.in_memory import InMemoryEventBus
from app.infrastructure.project_storage.filesystem import FilesystemProjectRepository
from app.infrastructure.sqlite.runtime_repository import SqliteRuntimeRepository
from app.runtime.factory import RuntimeRepositories, StandardRuntimeFactory
from app.runtime.service import RuntimeService
from tests.fakes.telegram import FakeTelegramPort


class RuntimeHarness:
    def __init__(
        self,
        *,
        project: BotProject,
        root: Path,
        flow: Flow,
        projects: FilesystemProjectRepository,
        runtime: SqliteRuntimeRepository,
        telegram: FakeTelegramPort,
        events: InMemoryEventBus,
        service: RuntimeService,
    ) -> None:
        self.project = project
        self.root = root
        self.flow = flow
        self.projects = projects
        self.runtime = runtime
        self.telegram = telegram
        self.events = events
        self.service = service


def build_harness(
    root: Path,
    flow: Flow,
    *,
    telegram: FakeTelegramPort | None = None,
    project: BotProject | None = None,
) -> RuntimeHarness:
    projects = FilesystemProjectRepository()
    identity = BotIdentity(
        bot_id=1001,
        username="studio_test_bot",
        display_name="Studio Test Bot",
    )
    project = project or replace(
        BotProject.create("Runtime Test"),
        configuration=BotConfiguration(
            secret_ref="test-token",
            start_flow_id=flow.id,
            identity=identity,
        ),
    )
    if not (root / "bot.json").exists():
        projects.create(root, project)
    projects.save_flow(root, flow)
    runtime = SqliteRuntimeRepository.from_project(root)
    fake = telegram or FakeTelegramPort(identity)
    events = InMemoryEventBus()
    factory = StandardRuntimeFactory(
        projects=projects,
        telegram_factory=lambda _token: fake,
        repository_factory=lambda _root: RuntimeRepositories(
            sessions=runtime,
            storage=runtime,
        ),
        publisher=events,
    )
    service = factory(project, root, "not-a-real-token")
    return RuntimeHarness(
        project=project,
        root=root,
        flow=flow,
        projects=projects,
        runtime=runtime,
        telegram=fake,
        events=events,
        service=service,
    )

