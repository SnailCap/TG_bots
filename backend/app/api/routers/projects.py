from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.workspace.custom_emoji import (
    DEFAULT_FALLBACK_EMOJI,
    CustomEmojiRequestError,
    CustomEmojiSource,
)
from app.workspace.preview_message import (
    PreviewMessageCompileError,
    PreviewMessageDeliveryError,
)
from app.workspace.service import ProjectService, WorkspaceError


router = APIRouter(prefix="/projects", tags=["projects"])


class OpenProjectRequest(BaseModel):
    root_path: str


class CreateProjectRequest(BaseModel):
    parent_path: str
    name: str = Field(min_length=1, max_length=80)
    package_name: str | None = Field(default=None, max_length=80)


class ResourceCreateRequest(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)


class ViewCreateRequest(ResourceCreateRequest):
    text_content: str | None = None
    content_document: dict[str, Any] | None = None


class DisplayNameRequest(BaseModel):
    kind: Literal["views", "flows", "schedules", "handlers", "commands"]
    key: str = Field(min_length=1, max_length=512)
    name: str = Field(min_length=1, max_length=160)
    revision: str


class ResourceSaveRequest(BaseModel):
    payload: dict[str, Any]
    revision: str


class VariableCatalogSaveRequest(BaseModel):
    payload: dict[str, Any]
    revision: str | None = None


class ViewSaveRequest(ResourceSaveRequest):
    text_content: str
    text_revision: str | None


class ViewContentSaveRequest(ResourceSaveRequest):
    document: dict[str, Any]
    document_revision: str | None = None
    text_revision: str | None = None


class ContentCompileRequest(BaseModel):
    document: dict[str, Any]
    variables: dict[str, Any] = Field(default_factory=dict)
    split_long_messages: bool = True


class PreviewMessageSendRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document: dict[str, Any]
    variables: dict[str, Any] = Field(default_factory=dict)
    chat_id: int | str = Field(
        validation_alias=AliasChoices("chatId", "chat_id"),
        serialization_alias="chatId",
    )
    split_long_messages: bool = Field(
        default=True,
        validation_alias=AliasChoices("splitLongMessages", "split_long_messages"),
        serialization_alias="splitLongMessages",
    )

    @field_validator("chat_id", mode="before")
    @classmethod
    def reject_boolean_chat_id(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("chatId must be an integer or non-empty string.")
        return value


class ContentDiagnosticResponse(BaseModel):
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    path: str | None = None


class PreviewMessageSendResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sent: Literal[True]
    sent_count: int = Field(
        validation_alias=AliasChoices("sentCount", "sent_count"),
        serialization_alias="sentCount",
    )
    total_count: int = Field(
        validation_alias=AliasChoices("totalCount", "total_count"),
        serialization_alias="totalCount",
    )
    message_ids: list[int | None] = Field(
        validation_alias=AliasChoices("messageIds", "message_ids"),
        serialization_alias="messageIds",
    )
    warnings: list[ContentDiagnosticResponse] = Field(default_factory=list)


class ResourceRenameRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    revision: str


class PreviewRequest(BaseModel):
    payload: dict[str, Any]


class ProjectSettingsSaveRequest(BaseModel):
    telegram_bot_token: str | None = Field(default=None, max_length=4096)
    clear_telegram_bot_token: bool = False
    revision: str | None = None


class CustomEmojiResolveRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    custom_emoji_ids: list[str] = Field(
        min_length=1,
        max_length=200,
        validation_alias=AliasChoices("customEmojiIds", "custom_emoji_ids", "ids"),
        serialization_alias="customEmojiIds",
    )
    fallback_by_id: dict[str, str] = Field(
        default_factory=dict,
        max_length=200,
        validation_alias=AliasChoices("fallbackById", "fallback_by_id"),
        serialization_alias="fallbackById",
    )
    source: CustomEmojiSource = "manual-id"


class CustomEmojiCapabilityTestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    custom_emoji_id: str = Field(
        validation_alias=AliasChoices("customEmojiId", "custom_emoji_id", "id"),
        serialization_alias="customEmojiId",
    )
    chat_id: int | str = Field(
        validation_alias=AliasChoices("chatId", "chat_id"),
        serialization_alias="chatId",
    )
    fallback_emoji: str = Field(
        default=DEFAULT_FALLBACK_EMOJI,
        max_length=32,
        validation_alias=AliasChoices("fallbackEmoji", "fallback_emoji", "fallback"),
        serialization_alias="fallbackEmoji",
    )


class UserUpdateRequest(BaseModel):
    role: Literal["user", "trusted", "moderator", "administrator"]
    blocked: bool
    note: str = Field(default="", max_length=10000)


class HandlerScaffoldRequest(BaseModel):
    handler_id: str = Field(min_length=1, max_length=128)
    kind: str
    registry_revision: str
    outcomes: list[str] = Field(default_factory=list)
    description: str | None = None
    attachment: dict[str, Any] | None = None
    target_revision: str | None = None
    routes: dict[str, Any] = Field(default_factory=dict)


class HandlerRepairRequest(BaseModel):
    registry_revision: str


class HandlerDetachRequest(BaseModel):
    attachment: dict[str, Any]
    target_revision: str


def service(request: Request) -> ProjectService:
    return request.app.state.project_service


def fail(error: WorkspaceError) -> None:
    raise HTTPException(
        error.status_code,
        {"code": error.code, "message": str(error)},
    ) from error


def fail_custom_emoji(error: CustomEmojiRequestError) -> None:
    raise HTTPException(
        422,
        {"code": error.code, "message": str(error)},
    ) from error


def fail_preview_message(error: WorkspaceError) -> None:
    detail: dict[str, Any] = {"code": error.code, "message": str(error)}
    if isinstance(error, PreviewMessageCompileError):
        detail["errors"] = [
            {
                "severity": item.severity,
                "code": item.code,
                "message": item.message,
                **({"path": item.path} if item.path is not None else {}),
            }
            for item in error.diagnostics
        ]
    elif isinstance(error, PreviewMessageDeliveryError):
        detail["sentCount"] = error.sent_count
        detail["totalCount"] = error.total_count
    raise HTTPException(error.status_code, detail) from error


@router.post("/open")
async def open_project(body: OpenProjectRequest, request: Request) -> dict[str, Any]:
    try:
        return service(request).open_project(body.root_path)
    except WorkspaceError as error:
        fail(error)


@router.post("")
async def create_project(body: CreateProjectRequest, request: Request) -> dict[str, Any]:
    try:
        return service(request).create_starter(
            parent_path=body.parent_path,
            name=body.name,
            package_name=body.package_name,
        )
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}")
async def describe(project_id: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).describe(project_id)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/display-names")
async def set_display_name(
    project_id: str, body: DisplayNameRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).set_display_name(
            project_id,
            kind=body.kind,
            key=body.key,
            name=body.name,
            revision=body.revision,
        )
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/users")
async def list_users(project_id: str, request: Request) -> list[dict[str, Any]]:
    try:
        return await service(request).list_users(project_id)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/users/{user_id}")
async def update_user(
    project_id: str, user_id: int, body: UserUpdateRequest, request: Request
) -> dict[str, Any]:
    try:
        return await service(request).update_user(
            project_id,
            user_id,
            role=body.role,
            blocked=body.blocked,
            note=body.note,
        )
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/users/{user_id}/avatar")
async def get_user_avatar(
    project_id: str, user_id: int, request: Request
) -> Response:
    try:
        avatar = await service(request).get_user_avatar(project_id, user_id)
        return Response(
            content=avatar.data,
            media_type=avatar.mime_type,
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/settings")
async def get_project_settings(project_id: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).get_project_settings(project_id)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/settings")
async def save_project_settings(
    project_id: str, body: ProjectSettingsSaveRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).save_project_settings(
            project_id,
            telegram_bot_token=body.telegram_bot_token,
            clear_telegram_bot_token=body.clear_telegram_bot_token,
            revision=body.revision,
        )
    except WorkspaceError as error:
        fail(error)


# Telegram custom emoji ---------------------------------------------------------------


@router.post("/{project_id}/telegram/custom-emojis/resolve")
async def resolve_custom_emojis(
    project_id: str, body: CustomEmojiResolveRequest, request: Request
) -> dict[str, Any]:
    try:
        return await service(request).resolve_custom_emojis(
            project_id,
            body.custom_emoji_ids,
            fallback_by_id=body.fallback_by_id,
            source=body.source,
        )
    except CustomEmojiRequestError as error:
        fail_custom_emoji(error)
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/telegram/custom-emojis/{custom_emoji_id}/preview")
async def get_custom_emoji_preview(
    project_id: str, custom_emoji_id: str, request: Request
) -> Response:
    try:
        preview = service(request).get_custom_emoji_preview(
            project_id, custom_emoji_id
        )
        return FileResponse(
            path=preview.path,
            media_type=preview.mime_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Content-Type-Options": "nosniff",
            },
        )
    except CustomEmojiRequestError as error:
        fail_custom_emoji(error)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/telegram/custom-emojis/capability-test")
async def test_custom_emoji_capability(
    project_id: str, body: CustomEmojiCapabilityTestRequest, request: Request
) -> dict[str, Any]:
    try:
        return await service(request).test_custom_emoji_capability(
            project_id,
            body.custom_emoji_id,
            chat_id=body.chat_id,
            fallback_emoji=body.fallback_emoji,
        )
    except CustomEmojiRequestError as error:
        fail_custom_emoji(error)
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/manifest")
async def get_manifest(project_id: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).get_manifest(project_id)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/manifest")
async def save_manifest(
    project_id: str, body: ResourceSaveRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).save_manifest(
            project_id, body.payload, body.revision
        )
    except WorkspaceError as error:
        fail(error)


# Views --------------------------------------------------------------------------------


@router.get("/{project_id}/views")
async def list_views(project_id: str, request: Request) -> list[dict[str, Any]]:
    try:
        return service(request).list_views(project_id)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/views")
async def create_view(
    project_id: str, body: ViewCreateRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).create_view(
            project_id,
            body.id,
            body.payload,
            name=body.name,
            text_content=body.text_content,
            content_document=body.content_document,
        )
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/views/{view_id}")
async def get_view(project_id: str, view_id: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).get_view(project_id, view_id)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/views/{view_id}")
async def save_view(
    project_id: str,
    view_id: str,
    body: ViewSaveRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).save_view(
            project_id,
            view_id,
            body.payload,
            body.revision,
            text_content=body.text_content,
            text_revision=body.text_revision,
        )
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/views/{view_id}/content")
async def save_view_content(
    project_id: str,
    view_id: str,
    body: ViewContentSaveRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).save_view_content(
            project_id,
            view_id,
            body.payload,
            body.revision,
            document=body.document,
            document_revision=body.document_revision,
            text_revision=body.text_revision,
        )
    except WorkspaceError as error:
        fail(error)


@router.delete("/{project_id}/views/{view_id}")
async def delete_view(
    project_id: str, view_id: str, revision: str, request: Request
) -> Response:
    try:
        service(request).delete_view(project_id, view_id, revision)
        return Response(status_code=204)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/views/{view_id}/rename")
async def rename_view(
    project_id: str, view_id: str, body: ResourceRenameRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).rename_view(project_id, view_id, body.id, body.revision)
    except WorkspaceError as error:
        fail(error)


# Flows --------------------------------------------------------------------------------


@router.get("/{project_id}/flows")
async def list_flows(project_id: str, request: Request) -> list[dict[str, Any]]:
    try:
        return service(request).list_flows(project_id)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/flows")
async def create_flow(
    project_id: str, body: ResourceCreateRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).create_flow(project_id, body.id, body.payload, name=body.name)
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/flows/{flow_id}")
async def get_flow(project_id: str, flow_id: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).get_flow(project_id, flow_id)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/flows/{flow_id}")
async def save_flow(
    project_id: str,
    flow_id: str,
    body: ResourceSaveRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).save_flow(
            project_id, flow_id, body.payload, body.revision
        )
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/flows/{flow_id}/rename")
async def rename_flow(
    project_id: str, flow_id: str, body: ResourceRenameRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).rename_flow(project_id, flow_id, body.id, body.revision)
    except WorkspaceError as error:
        fail(error)


@router.delete("/{project_id}/flows/{flow_id}")
async def delete_flow(
    project_id: str, flow_id: str, revision: str, request: Request
) -> Response:
    try:
        service(request).delete_flow(project_id, flow_id, revision)
        return Response(status_code=204)
    except WorkspaceError as error:
        fail(error)


# Commands -----------------------------------------------------------------------------


@router.get("/{project_id}/commands")
async def get_commands(project_id: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).get_commands(project_id)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/commands")
async def save_commands(
    project_id: str, body: ResourceSaveRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).save_commands(
            project_id, body.payload, body.revision
        )
    except WorkspaceError as error:
        fail(error)


# Schedules ----------------------------------------------------------------------------


@router.get("/{project_id}/schedules")
async def list_schedules(project_id: str, request: Request) -> list[dict[str, Any]]:
    try:
        return service(request).list_schedules(project_id)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/schedules")
async def create_schedule(
    project_id: str, body: ResourceCreateRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).create_schedule(project_id, body.id, body.payload, name=body.name)
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/schedules/{schedule_id}")
async def get_schedule(
    project_id: str, schedule_id: str, request: Request
) -> dict[str, Any]:
    try:
        return service(request).get_schedule(project_id, schedule_id)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/schedules/{schedule_id}")
async def save_schedule(
    project_id: str,
    schedule_id: str,
    body: ResourceSaveRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).save_schedule(
            project_id, schedule_id, body.payload, body.revision
        )
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/schedules/{schedule_id}/rename")
async def rename_schedule(
    project_id: str, schedule_id: str, body: ResourceRenameRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).rename_schedule(
            project_id, schedule_id, body.id, body.revision
        )
    except WorkspaceError as error:
        fail(error)


@router.delete("/{project_id}/schedules/{schedule_id}")
async def delete_schedule(
    project_id: str, schedule_id: str, revision: str, request: Request
) -> Response:
    try:
        service(request).delete_schedule(project_id, schedule_id, revision)
        return Response(status_code=204)
    except WorkspaceError as error:
        fail(error)


# Handlers -----------------------------------------------------------------------------


@router.get("/{project_id}/handlers")
async def list_handlers(project_id: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).list_handlers(project_id)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/handlers")
async def scaffold_handler(
    project_id: str, body: HandlerScaffoldRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).scaffold_handler(
            project_id,
            handler_id=body.handler_id,
            kind=body.kind,
            outcomes=body.outcomes,
            description=body.description,
            registry_revision=body.registry_revision,
            attachment=body.attachment,
            target_revision=body.target_revision,
            routes=body.routes,
        )
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/handlers/{handler_id}/usages")
async def handler_usages(
    project_id: str, handler_id: str, request: Request
) -> dict[str, Any]:
    try:
        return {
            "handler_id": handler_id,
            "usages": service(request).handler_usages(project_id, handler_id),
        }
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/handlers/{handler_id}/source")
async def handler_source(
    project_id: str, handler_id: str, request: Request
) -> dict[str, Any]:
    try:
        return service(request).handler_source(project_id, handler_id)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/handlers/{handler_id}/detach")
async def detach_handler(
    project_id: str,
    handler_id: str,
    body: HandlerDetachRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).detach_handler(
            project_id,
            handler_id,
            attachment=body.attachment,
            target_revision=body.target_revision,
        )
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/handlers/{handler_id}/repair")
async def repair_handler(
    project_id: str,
    handler_id: str,
    body: HandlerRepairRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).repair_handler(
            project_id,
            handler_id,
            registry_revision=body.registry_revision,
        )
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/handlers/{handler_id}/open")
async def open_handler(
    project_id: str, handler_id: str, request: Request
) -> dict[str, Any]:
    """Resolve an IDE target. Electron owns process launch and repeats containment checks."""

    try:
        return service(request).handler_source(project_id, handler_id)
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/handlers/{handler_id}")
async def get_handler(
    project_id: str, handler_id: str, request: Request
) -> dict[str, Any]:
    try:
        return service(request).get_handler(project_id, handler_id)
    except WorkspaceError as error:
        fail(error)


@router.post("/{project_id}/handlers/{handler_id}/rename")
async def rename_handler(
    project_id: str, handler_id: str, body: ResourceRenameRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).rename_handler(
            project_id, handler_id, body.id, body.revision
        )
    except WorkspaceError as error:
        fail(error)


@router.delete("/{project_id}/handlers/{handler_id}")
async def delete_handler(
    project_id: str, handler_id: str, revision: str, request: Request
) -> Response:
    try:
        service(request).delete_handler(project_id, handler_id, revision)
        return Response(status_code=204)
    except WorkspaceError as error:
        fail(error)


# Preview and validation ---------------------------------------------------------------


@router.post("/{project_id}/content/compile")
async def compile_content(
    project_id: str, body: ContentCompileRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).compile_content(
            project_id,
            body.document,
            variables=body.variables,
            split_long_messages=body.split_long_messages,
        )
    except WorkspaceError as error:
        fail(error)


# Resource variables -------------------------------------------------------------------


@router.get("/{project_id}/variables")
async def get_variables(
    project_id: str,
    request: Request,
    resource_type: str | None = None,
    resource_id: str | None = None,
    flow_id: str | None = None,
    state_id: str | None = None,
    handler_id: str | None = None,
) -> dict[str, Any]:
    try:
        return service(request).get_variables(
            project_id,
            resource_type=resource_type,
            resource_id=resource_id,
            flow_id=flow_id,
            state_id=state_id,
            handler_id=handler_id,
        )
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/variables")
async def save_variables(
    project_id: str, body: VariableCatalogSaveRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).save_variables(project_id, body.payload, body.revision)
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/variables/{variable_id}/usages")
async def get_variable_usages(
    project_id: str, variable_id: str, request: Request
) -> dict[str, Any]:
    try:
        return {"usages": service(request).variable_usages(project_id, variable_id)}
    except WorkspaceError as error:
        fail(error)


@router.post(
    "/{project_id}/content/send-preview",
    response_model=PreviewMessageSendResponse,
)
async def send_preview_message(
    project_id: str,
    body: PreviewMessageSendRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return await service(request).send_preview_message(
            project_id,
            body.document,
            variables=body.variables,
            chat_id=body.chat_id,
            split_long_messages=body.split_long_messages,
        )
    except WorkspaceError as error:
        fail_preview_message(error)


@router.post("/{project_id}/preview")
async def preview(
    project_id: str, body: PreviewRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).preview(project_id, body.payload)
    except WorkspaceError as error:
        fail(error)


@router.get("/{project_id}/validation")
async def validation(project_id: str, request: Request) -> dict[str, Any]:
    try:
        return {"issues": service(request).validate(project_id)}
    except WorkspaceError as error:
        fail(error)
