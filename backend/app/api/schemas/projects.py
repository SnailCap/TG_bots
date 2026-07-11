from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.domain.project import BotConfiguration, BotProject, ProjectTreeEntry, RecentProject

from .common import ApiModel


class BotIdentityResponse(ApiModel):
    bot_id: int
    username: str
    display_name: str


class BotConfigurationResponse(ApiModel):
    secret_configured: bool
    secret_ref: str | None
    start_flow_id: str | None
    start_behavior: str
    identity: BotIdentityResponse | None
    metadata: dict


class ProjectResponse(ApiModel):
    id: str
    name: str
    path: str
    schema_version: int
    created_at: datetime
    updated_at: datetime
    configuration: BotConfigurationResponse


class ProjectSummaryResponse(ApiModel):
    id: str
    name: str
    path: str
    updated_at: datetime | None = None
    exists: bool = True


class CreateProjectRequest(ApiModel):
    directory: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)


class OpenProjectRequest(ApiModel):
    path: str = Field(min_length=1)


class PatchProjectRequest(ApiModel):
    name: str = Field(min_length=1, max_length=200)


class RecentProjectResponse(ApiModel):
    project_id: str
    name: str
    path: str
    last_opened_at: datetime
    exists: bool


class TreeEntryResponse(ApiModel):
    id: str
    name: str
    path: str
    kind: str
    size: int | None = None
    children: list["TreeEntryResponse"] = Field(default_factory=list)


class CreateTreeItemRequest(ApiModel):
    kind: str
    path: str = Field(min_length=1)


class RenameTreeItemRequest(ApiModel):
    path: str = Field(min_length=1)
    new_path: str = Field(min_length=1)


class DeleteTreeItemRequest(ApiModel):
    path: str = Field(min_length=1)


def configuration_response(value: BotConfiguration) -> BotConfigurationResponse:
    identity = value.identity
    return BotConfigurationResponse(
        secret_configured=value.secret_ref is not None,
        secret_ref=value.secret_ref,
        start_flow_id=value.start_flow_id,
        start_behavior=value.start_behavior,
        identity=(
            BotIdentityResponse(
                bot_id=identity.bot_id,
                username=identity.username,
                display_name=identity.display_name,
            )
            if identity is not None
            else None
        ),
        metadata=dict(value.metadata),
    )


def project_response(project: BotProject, path: str) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        name=project.name,
        path=path,
        schema_version=project.schema_version,
        created_at=project.created_at,
        updated_at=project.updated_at,
        configuration=configuration_response(project.configuration),
    )


def recent_response(value: RecentProject) -> RecentProjectResponse:
    return RecentProjectResponse(
        project_id=value.project_id,
        name=value.name,
        path=value.path,
        last_opened_at=value.last_opened_at,
        exists=value.exists,
    )


def tree_response(value: ProjectTreeEntry) -> TreeEntryResponse:
    return TreeEntryResponse(
        id=value.id,
        name=value.name,
        path=value.path,
        kind=value.kind,
        size=value.size,
        children=[tree_response(child) for child in value.children],
    )
