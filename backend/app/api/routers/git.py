from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.integrations.git.errors import GitIntegrationError
from app.integrations.git.models import (
    GitConnectRequest,
    GitCreateRepositoryRequest,
    GitOperationRequest,
    GitPublishRequest,
    GitPushRequest,
)
from app.integrations.git.service import GitService
from app.workspace.repository import WorkspaceError


router = APIRouter(prefix="/projects/{project_id}/git", tags=["git"])


def service(request: Request) -> GitService:
    return request.app.state.git_service


def fail(error: GitIntegrationError | WorkspaceError) -> None:
    detail = {"code": error.code, "message": str(error)}
    if isinstance(error, GitIntegrationError) and error.details:
        detail["details"] = error.details
    raise HTTPException(error.status_code, detail) from error


@router.get("/status")
async def status(project_id: str, request: Request) -> dict:
    try:
        return service(request).status(project_id)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.get("/changes")
async def changes(project_id: str, request: Request) -> dict:
    try:
        return service(request).changes(project_id)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.get("/history")
async def history(
    project_id: str,
    request: Request,
    limit: int = Query(default=30, ge=1, le=100),
) -> dict:
    try:
        return service(request).history(project_id, limit)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.post("/connect")
async def connect(project_id: str, body: GitConnectRequest, request: Request) -> dict:
    try:
        return service(request).connect(project_id, body)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.post("/create-repository")
async def create_repository(
    project_id: str, body: GitCreateRepositoryRequest, request: Request
) -> dict:
    try:
        return service(request).create_repository(project_id, body)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.post("/disconnect")
async def disconnect(project_id: str, request: Request) -> dict:
    try:
        return service(request).disconnect(project_id)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.post("/fetch")
async def fetch(project_id: str, body: GitOperationRequest, request: Request) -> dict:
    try:
        return service(request).fetch(project_id, body.token)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.post("/sync")
async def sync(project_id: str, body: GitOperationRequest, request: Request) -> dict:
    try:
        return service(request).sync(project_id, body.token)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.post("/push")
async def push(project_id: str, body: GitPushRequest, request: Request) -> dict:
    try:
        return service(request).push(project_id, body)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)


@router.post("/publish")
async def publish(project_id: str, body: GitPublishRequest, request: Request) -> dict:
    try:
        return service(request).publish(project_id, body)
    except (GitIntegrationError, WorkspaceError) as error:
        fail(error)

