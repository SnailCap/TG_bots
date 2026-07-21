from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.workspace.service import ProjectService, WorkspaceError


router = APIRouter(prefix="/projects", tags=["projects"])


class OpenProjectRequest(BaseModel):
    root_path: str


class CreateProjectRequest(BaseModel):
    parent_path: str
    name: str = Field(min_length=1, max_length=80)
    package_name: str | None = Field(default=None, max_length=80)


class ResourceCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]


class ResourceSaveRequest(BaseModel):
    payload: dict[str, Any]
    revision: str


class ResourceRenameRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    revision: str


class TemplateSaveRequest(BaseModel):
    content: str
    revision: str | None = None


class PreviewRequest(BaseModel):
    payload: dict[str, Any]


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
    project_id: str, body: ResourceCreateRequest, request: Request
) -> dict[str, Any]:
    try:
        return service(request).create_view(project_id, body.id, body.payload)
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
    body: ResourceSaveRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).save_view(
            project_id, view_id, body.payload, body.revision
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
        return service(request).create_flow(project_id, body.id, body.payload)
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
        return service(request).create_schedule(project_id, body.id, body.payload)
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


@router.delete("/{project_id}/handlers/{handler_id}")
async def delete_handler(
    project_id: str, handler_id: str, revision: str, request: Request
) -> Response:
    try:
        service(request).delete_handler(project_id, handler_id, revision)
        return Response(status_code=204)
    except WorkspaceError as error:
        fail(error)


# Templates, preview and validation ----------------------------------------------------


@router.get("/{project_id}/templates/{path:path}")
async def get_template(project_id: str, path: str, request: Request) -> dict[str, Any]:
    try:
        return service(request).get_template(project_id, path)
    except WorkspaceError as error:
        fail(error)


@router.put("/{project_id}/templates/{path:path}")
async def save_template(
    project_id: str,
    path: str,
    body: TemplateSaveRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return service(request).save_template(
            project_id, path, body.content, body.revision
        )
    except WorkspaceError as error:
        fail(error)


@router.delete("/{project_id}/templates/{path:path}")
async def delete_template(
    project_id: str, path: str, revision: str, request: Request
) -> Response:
    try:
        service(request).delete_template(project_id, path, revision)
        return Response(status_code=204)
    except WorkspaceError as error:
        fail(error)


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
