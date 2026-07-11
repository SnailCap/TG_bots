from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any

from app.application import (
    AssetApplicationService,
    FlowApplicationService,
    FlowValidator,
    ProjectApplicationService,
    ProjectValidator,
    ScriptApplicationService,
    SettingsApplicationService,
    ValidationApplicationService,
)
from app.domain.ports.secrets import SecretStore
from app.domain.ports.sessions import RuntimeStorage
from app.domain.ports.token_validator import BotTokenValidator
from app.domain.ports.projects import ProjectRepository
from app.infrastructure.events import InMemoryEventBus
from app.infrastructure.project_storage import (
    FilesystemProjectRepository,
    JsonRecentProjectsRepository,
)
from app.infrastructure.scripts import ScriptDiscovery
from app.infrastructure.secrets import KeyringSecretStore
from app.infrastructure.telegram import PtbBotTokenValidator, PtbLongPollingAdapter
from app.infrastructure.sqlite import SqliteRuntimeRepository
from app.runtime import RuntimeManager, RuntimeRepositories, StandardRuntimeFactory


@dataclass(slots=True)
class AppContainer:
    projects: ProjectApplicationService
    flows: FlowApplicationService
    settings: SettingsApplicationService
    scripts: ScriptApplicationService
    assets: AssetApplicationService
    validation: ValidationApplicationService
    events: InMemoryEventBus
    secret_store: SecretStore
    project_repository: ProjectRepository
    runtime_storage_factory: Callable[[Path], RuntimeStorage]
    runtime_manager: RuntimeManager

    @classmethod
    def build(
        cls,
        *,
        data_dir: Path,
        secret_store: SecretStore,
        token_validator: BotTokenValidator,
        runtime_manager: RuntimeManager | None = None,
        runtime_storage_factory: Callable[[Path], RuntimeStorage] | None = None,
    ) -> "AppContainer":
        repository = FilesystemProjectRepository()
        recent = JsonRecentProjectsRepository(data_dir / "recent-projects.json")
        events = InMemoryEventBus()
        discovery = ScriptDiscovery()
        projects = ProjectApplicationService(repository, recent, events)
        flows = FlowApplicationService(projects, repository, events)
        settings = SettingsApplicationService(
            projects,
            flows,
            secret_store,
            token_validator,
            events,
        )
        scripts = ScriptApplicationService(projects, repository, discovery, events)
        assets = AssetApplicationService(projects, repository, events)
        validation = ValidationApplicationService(
            projects,
            repository,
            discovery,
            ProjectValidator(FlowValidator()),
        )
        storage_factory = (
            runtime_storage_factory
            or (lambda project_root: SqliteRuntimeRepository.from_project(project_root))
        )

        if runtime_manager is None:
            def runtime_repositories(project_root: Path) -> RuntimeRepositories:
                repository_instance = SqliteRuntimeRepository.from_project(project_root)
                return RuntimeRepositories(
                    sessions=repository_instance,
                    storage=repository_instance,
                )

            runtime_manager = RuntimeManager(
                StandardRuntimeFactory(
                    projects=repository,
                    telegram_factory=PtbLongPollingAdapter,
                    repository_factory=runtime_repositories,
                    publisher=events,
                )
            )

        return cls(
            projects=projects,
            flows=flows,
            settings=settings,
            scripts=scripts,
            assets=assets,
            validation=validation,
            events=events,
            secret_store=secret_store,
            project_repository=repository,
            runtime_storage_factory=storage_factory,
            runtime_manager=runtime_manager,
        )


def default_data_dir() -> Path:
    configured = os.getenv("BOTSTUDIO_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "TelegramBotStudio"
    return Path.home() / ".telegram-bot-studio"


def create_default_container() -> AppContainer:
    return AppContainer.build(
        data_dir=default_data_dir(),
        secret_store=KeyringSecretStore(),
        token_validator=PtbBotTokenValidator(),
    )
