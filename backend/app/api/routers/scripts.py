from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.scripts import (
    ActionUsageResponse,
    ActionsResponse,
    CreateScriptRequest,
    RenameFileRequest,
    SaveScriptRequest,
    ScriptContentResponse,
    ScriptPathResponse,
    SearchMatchResponse,
    ValidateScriptRequest,
    action_response,
    issue_response,
)

router = APIRouter(prefix="/projects/{project_id}/scripts", tags=["scripts"])


@router.get("", response_model=list[ScriptPathResponse])
async def list_scripts(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> list[ScriptPathResponse]:
    return [ScriptPathResponse(path=path) for path in container.scripts.list(project_id)]


@router.get("/content", response_model=ScriptContentResponse)
async def read_script(
    project_id: str,
    path: str = Query(min_length=1),
    container: AppContainer = Depends(get_container),
) -> ScriptContentResponse:
    return ScriptContentResponse(
        path=path,
        name=PurePosixPath(path).name,
        content=container.scripts.read(project_id, path),
    )


@router.get("/search", response_model=list[SearchMatchResponse])
async def search_scripts(
    project_id: str,
    q: str = Query(min_length=1),
    limit: int = Query(default=200, ge=1, le=1_000),
    container: AppContainer = Depends(get_container),
) -> list[SearchMatchResponse]:
    return [
        SearchMatchResponse(
            path=item.path,
            line=item.line,
            column=item.column,
            preview=item.preview,
        )
        for item in container.scripts.search(project_id, q, limit=limit)
    ]


@router.get("/actions", response_model=ActionsResponse)
async def list_actions(
    project_id: str,
    validate_imports: bool = True,
    container: AppContainer = Depends(get_container),
) -> ActionsResponse:
    result = container.scripts.actions(
        project_id,
        validate_imports=validate_imports,
    )
    return ActionsResponse(
        actions=[action_response(item) for item in result.actions],
        issues=[issue_response(item) for item in result.issues],
        valid=result.is_valid,
    )


@router.get("/actions/{action_name}/usages", response_model=list[ActionUsageResponse])
async def action_usages(
    project_id: str,
    action_name: str,
    container: AppContainer = Depends(get_container),
) -> list[ActionUsageResponse]:
    return [
        ActionUsageResponse(
            action_name=item.action_name,
            flow_id=item.flow_id,
            flow_name=item.flow_name,
            node_id=item.node_id,
            node_name=item.node_name,
        )
        for item in container.scripts.usages(project_id, action_name)
    ]


@router.post("", response_model=ScriptContentResponse, status_code=201)
async def create_script(
    project_id: str,
    payload: CreateScriptRequest,
    container: AppContainer = Depends(get_container),
) -> ScriptContentResponse:
    path = await container.scripts.create(project_id, payload.path, payload.content)
    return ScriptContentResponse(
        path=path,
        name=PurePosixPath(path).name,
        content=container.scripts.read(project_id, path),
    )


@router.put("", response_model=ScriptPathResponse)
async def save_script(
    project_id: str,
    payload: SaveScriptRequest,
    container: AppContainer = Depends(get_container),
) -> ScriptPathResponse:
    path = await container.scripts.save(project_id, payload.path, payload.content)
    return ScriptPathResponse(path=path)


@router.patch("", response_model=ScriptPathResponse)
async def rename_script(
    project_id: str,
    payload: RenameFileRequest,
    container: AppContainer = Depends(get_container),
) -> ScriptPathResponse:
    path = await container.scripts.rename(project_id, payload.path, payload.new_path)
    return ScriptPathResponse(path=path)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script(
    project_id: str,
    path: str = Query(min_length=1),
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.scripts.delete(project_id, path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/validate", response_model=ActionsResponse)
async def validate_script_payload(
    project_id: str,
    payload: ValidateScriptRequest,
    container: AppContainer = Depends(get_container),
) -> ActionsResponse:
    if payload.path is None:
        raise ValueError("Script path is required")
    result = container.scripts.validate_source(project_id, payload.path, payload.content)
    return ActionsResponse(
        actions=[action_response(item) for item in result.actions],
        issues=[issue_response(item) for item in result.issues],
        valid=result.is_valid,
    )


@router.post("/{script_path:path}/validate", response_model=ActionsResponse)
async def validate_script_at_path(
    project_id: str,
    script_path: str,
    payload: ValidateScriptRequest,
    container: AppContainer = Depends(get_container),
) -> ActionsResponse:
    result = container.scripts.validate_source(project_id, script_path, payload.content)
    return ActionsResponse(
        actions=[action_response(item) for item in result.actions],
        issues=[issue_response(item) for item in result.issues],
        valid=result.is_valid,
    )


@router.get("/{script_path:path}", response_model=ScriptContentResponse)
async def read_script_at_path(
    project_id: str,
    script_path: str,
    container: AppContainer = Depends(get_container),
) -> ScriptContentResponse:
    return ScriptContentResponse(
        path=script_path,
        name=PurePosixPath(script_path).name,
        content=container.scripts.read(project_id, script_path),
    )


@router.put("/{script_path:path}", response_model=ScriptContentResponse)
@router.patch("/{script_path:path}", response_model=ScriptContentResponse)
async def save_script_at_path(
    project_id: str,
    script_path: str,
    payload: SaveScriptRequest,
    container: AppContainer = Depends(get_container),
) -> ScriptContentResponse:
    if payload.path and payload.path != script_path:
        normalized_payload = payload.path.replace("\\", "/")
        normalized_route = script_path.replace("\\", "/")
        if normalized_payload != normalized_route:
            raise ValueError("Script path in URL and payload do not match")
    path = await container.scripts.save(project_id, script_path, payload.content)
    return ScriptContentResponse(
        path=path,
        name=PurePosixPath(path).name,
        content=container.scripts.read(project_id, path),
    )


@router.delete("/{script_path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_script_at_path(
    project_id: str,
    script_path: str,
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.scripts.delete(project_id, script_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
