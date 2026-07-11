from dataclasses import replace
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, Response, status

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.projects import (
    CreateProjectRequest,
    CreateTreeItemRequest,
    DeleteTreeItemRequest,
    OpenProjectRequest,
    PatchProjectRequest,
    ProjectResponse,
    ProjectSummaryResponse,
    RecentProjectResponse,
    TreeEntryResponse,
    RenameTreeItemRequest,
    project_response,
    recent_response,
    tree_response,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummaryResponse])
async def list_projects(
    container: AppContainer = Depends(get_container),
) -> list[ProjectSummaryResponse]:
    result: list[ProjectSummaryResponse] = []
    for item in container.projects.recent():
        updated_at = None
        name = item.name
        if item.exists:
            try:
                opened = container.projects.get(item.project_id)
                updated_at = opened.project.updated_at
                name = opened.project.name
            except Exception:
                pass
        result.append(
            ProjectSummaryResponse(
                id=item.project_id,
                name=name,
                path=item.path,
                updated_at=updated_at,
                exists=item.exists,
            )
        )
    return result


@router.get("/recent", response_model=list[RecentProjectResponse])
async def recent_projects(
    container: AppContainer = Depends(get_container),
) -> list[RecentProjectResponse]:
    return [recent_response(item) for item in container.projects.recent()]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    payload: CreateProjectRequest,
    container: AppContainer = Depends(get_container),
) -> ProjectResponse:
    opened = await container.projects.create(
        directory=payload.directory,
        name=payload.name,
    )
    return project_response(opened.project, str(opened.path))


@router.post("/open", response_model=ProjectResponse)
async def open_project(
    payload: OpenProjectRequest,
    container: AppContainer = Depends(get_container),
) -> ProjectResponse:
    opened = await container.projects.open(payload.path)
    return project_response(opened.project, str(opened.path))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> ProjectResponse:
    opened = container.projects.get(project_id)
    return project_response(opened.project, str(opened.path))


@router.patch("/{project_id}", response_model=ProjectResponse)
async def patch_project(
    project_id: str,
    payload: PatchProjectRequest,
    container: AppContainer = Depends(get_container),
) -> ProjectResponse:
    opened = await container.projects.rename(project_id, payload.name)
    return project_response(opened.project, str(opened.path))


@router.get("/{project_id}/tree", response_model=list[TreeEntryResponse])
async def project_tree(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> list[TreeEntryResponse]:
    return [tree_response(item) for item in container.projects.tree(project_id)]


@router.post("/{project_id}/tree", status_code=status.HTTP_204_NO_CONTENT)
async def create_tree_item(
    project_id: str,
    payload: CreateTreeItemRequest,
    container: AppContainer = Depends(get_container),
) -> Response:
    kind = payload.kind.casefold()
    if kind == "flow":
        name = PurePosixPath(payload.path).name.removesuffix(".flow.json")
        await container.flows.create(project_id, name=name)
    elif kind == "script":
        await container.scripts.create(project_id, payload.path)
    elif kind == "asset":
        await container.assets.create(project_id, payload.path, b"")
    else:
        raise ValueError(f"Unsupported tree item kind: {payload.kind}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{project_id}/tree", status_code=status.HTTP_204_NO_CONTENT)
async def rename_tree_item(
    project_id: str,
    payload: RenameTreeItemRequest,
    container: AppContainer = Depends(get_container),
) -> Response:
    path = payload.path.replace("\\", "/")
    if path.startswith("scripts/") or path.endswith(".py"):
        await container.scripts.rename(project_id, path, payload.new_path)
    elif path.startswith("assets/"):
        await container.assets.rename(
            project_id,
            path.removeprefix("assets/"),
            payload.new_path.removeprefix("assets/"),
        )
    elif path.startswith("flows/") and path.endswith(".flow.json"):
        flow_id = PurePosixPath(path).name.removesuffix(".flow.json")
        flow = container.flows.get(project_id, flow_id)
        new_name = PurePosixPath(payload.new_path).name.removesuffix(".flow.json")
        await container.flows.save(project_id, flow_id, replace(flow, name=new_name))
    else:
        raise ValueError(f"Unsupported tree item path: {payload.path}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{project_id}/tree", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tree_item(
    project_id: str,
    payload: DeleteTreeItemRequest,
    container: AppContainer = Depends(get_container),
) -> Response:
    path = payload.path.replace("\\", "/")
    if path.startswith("scripts/") or path.endswith(".py"):
        await container.scripts.delete(project_id, path)
    elif path.startswith("assets/"):
        await container.assets.delete(project_id, path.removeprefix("assets/"))
    elif path.startswith("flows/") and path.endswith(".flow.json"):
        flow_id = PurePosixPath(path).name.removesuffix(".flow.json")
        await container.flows.delete(project_id, flow_id)
    else:
        raise ValueError(f"Unsupported tree item path: {payload.path}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
