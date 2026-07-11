from __future__ import annotations

from dataclasses import replace

from app.domain.ports.events import EventPublisher
from app.domain.ports.secrets import SecretStore
from app.domain.ports.token_validator import BotTokenValidator
from app.domain.project import BotConfiguration, BotIdentity
from app.domain.runtime import RuntimeEvent
from app.errors import FlowNotFoundError, TokenValidationError

from .flows import FlowApplicationService
from .projects import ProjectApplicationService


class SettingsApplicationService:
    def __init__(
        self,
        projects: ProjectApplicationService,
        flows: FlowApplicationService,
        secrets: SecretStore,
        token_validator: BotTokenValidator,
        events: EventPublisher | None = None,
    ) -> None:
        self._projects = projects
        self._flows = flows
        self._secrets = secrets
        self._token_validator = token_validator
        self._events = events

    def get(self, project_id: str) -> BotConfiguration:
        return self._projects.get(project_id).project.configuration

    async def update(
        self,
        project_id: str,
        *,
        start_flow_id: str | None,
        start_behavior: str | None = None,
    ) -> BotConfiguration:
        opened = self._projects.get(project_id)
        if start_flow_id is not None:
            try:
                self._flows.get(project_id, start_flow_id)
            except FlowNotFoundError:
                raise
        behavior = start_behavior or opened.project.configuration.start_behavior
        if behavior not in {"reset", "resume"}:
            raise ValueError("start_behavior must be either 'reset' or 'resume'")
        configuration = replace(
            opened.project.configuration,
            start_flow_id=start_flow_id,
            start_behavior=behavior,
        )
        await self._projects.save_project(
            project_id,
            replace(opened.project, configuration=configuration),
        )
        await self._publish(project_id, "settings.updated", "Bot settings updated")
        return configuration

    async def set_token(self, project_id: str, token: str) -> BotConfiguration:
        normalized = token.strip()
        if not normalized:
            raise TokenValidationError("Telegram token must not be empty")
        identity = await self._token_validator.validate(normalized)
        opened = self._projects.get(project_id)
        secret_ref = (
            opened.project.configuration.secret_ref
            or f"botstudio:{project_id}:telegram-token"
        )
        self._secrets.set(secret_ref, normalized)
        configuration = replace(
            opened.project.configuration,
            secret_ref=secret_ref,
            identity=identity,
        )
        await self._projects.save_project(
            project_id,
            replace(opened.project, configuration=configuration),
        )
        await self._publish(
            project_id,
            "settings.token_validated",
            f"Telegram bot @{identity.username} validated",
        )
        return configuration

    async def clear_token(self, project_id: str) -> BotConfiguration:
        opened = self._projects.get(project_id)
        reference = opened.project.configuration.secret_ref
        if reference is not None:
            self._secrets.delete(reference)
        configuration = replace(
            opened.project.configuration,
            secret_ref=None,
            identity=None,
        )
        await self._projects.save_project(
            project_id,
            replace(opened.project, configuration=configuration),
        )
        await self._publish(project_id, "settings.token_cleared", "Telegram token removed")
        return configuration

    async def validate_saved_token(self, project_id: str) -> BotConfiguration:
        opened = self._projects.get(project_id)
        reference = opened.project.configuration.secret_ref
        if reference is None:
            raise TokenValidationError("Telegram token is not configured")
        token = self._secrets.get(reference)
        if token is None:
            raise TokenValidationError(
                "Telegram token reference exists, but the secret is unavailable"
            )
        identity = await self._token_validator.validate(token)
        configuration = replace(opened.project.configuration, identity=identity)
        await self._projects.save_project(
            project_id,
            replace(opened.project, configuration=configuration),
        )
        await self._publish(
            project_id,
            "settings.token_validated",
            f"Telegram bot @{identity.username} validated",
        )
        return configuration

    async def _publish(self, project_id: str, category: str, message: str) -> None:
        if self._events is not None:
            await self._events.publish(
                RuntimeEvent(project_id=project_id, category=category, message=message)
            )
