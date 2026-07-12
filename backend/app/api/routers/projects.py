from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.workspace.service import WorkspaceError, WorkspaceManager

router = APIRouter(prefix="/projects", tags=["projects"])


class OpenProjectRequest(BaseModel): root_path: str
class CreateProjectRequest(BaseModel):
    parent_path: str
    name: str = Field(min_length=1, max_length=80)
    package_name: str | None = Field(default=None, max_length=80)
class ViewCreateRequest(BaseModel):
    view_id: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any]
class ViewSaveRequest(BaseModel):
    payload: dict[str, Any]
    revision: str
class TemplateSaveRequest(BaseModel):
    content: str
    revision: str | None = None
class PreviewRequest(BaseModel): payload: dict[str, Any]


def manager(request: Request) -> WorkspaceManager: return request.app.state.workspace_manager
def fail(error: WorkspaceError) -> None: raise HTTPException(error.status_code, {"code": error.code, "message": str(error)}) from error


@router.post("/open")
async def open_project(body: OpenProjectRequest, request: Request) -> dict[str, Any]:
    try: return manager(request).open_project(body.root_path)
    except WorkspaceError as error: fail(error)

@router.post("")
async def create_project(body: CreateProjectRequest, request: Request) -> dict[str, Any]:
    try: return manager(request).create_starter(parent_path=body.parent_path, name=body.name, package_name=body.package_name)
    except WorkspaceError as error: fail(error)

@router.get("/{project_id}")
async def describe(project_id: str, request: Request) -> dict[str, Any]:
    try: return manager(request).describe(project_id)
    except WorkspaceError as error: fail(error)

@router.post("/{project_id}/views")
async def create_view(project_id: str, body: ViewCreateRequest, request: Request) -> dict[str, Any]:
    try: return manager(request).create_view(project_id, body.view_id, body.payload)
    except WorkspaceError as error: fail(error)

@router.get("/{project_id}/views/{view_id}")
async def get_view(project_id: str, view_id: str, request: Request) -> dict[str, Any]:
    try: return manager(request).get_view(project_id, view_id)
    except WorkspaceError as error: fail(error)

@router.put("/{project_id}/views/{view_id}")
async def save_view(project_id: str, view_id: str, body: ViewSaveRequest, request: Request) -> dict[str, Any]:
    try: return manager(request).save_view(project_id, view_id, body.payload, body.revision)
    except WorkspaceError as error: fail(error)

@router.delete("/{project_id}/views/{view_id}")
async def delete_view(project_id: str, view_id: str, revision: str, request: Request) -> Response:
    try:
        manager(request).delete_view(project_id, view_id, revision)
        return Response(status_code=204)
    except WorkspaceError as error: fail(error)

@router.get("/{project_id}/templates/{path:path}")
async def get_template(project_id: str, path: str, request: Request) -> dict[str, Any]:
    try: return manager(request).get_template(project_id, path)
    except WorkspaceError as error: fail(error)

@router.put("/{project_id}/templates/{path:path}")
async def save_template(project_id: str, path: str, body: TemplateSaveRequest, request: Request) -> dict[str, Any]:
    try: return manager(request).save_template(project_id, path, body.content, body.revision)
    except WorkspaceError as error: fail(error)

@router.post("/{project_id}/preview")
async def preview(project_id: str, body: PreviewRequest, request: Request) -> dict[str, Any]:
    try: return manager(request).preview(project_id, body.payload)
    except WorkspaceError as error: fail(error)

@router.get("/{project_id}/validation")
async def validation(project_id: str, request: Request) -> dict[str, Any]:
    try: return {"issues": manager(request).validate(project_id)}
    except WorkspaceError as error: fail(error)
