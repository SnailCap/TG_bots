from pathlib import PurePosixPath

from fastapi import APIRouter, Body, Depends, Query, Response, status

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.assets import AssetPathResponse, RenameAssetRequest

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])


@router.get("", response_model=list[AssetPathResponse])
async def list_assets(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> list[AssetPathResponse]:
    return [AssetPathResponse(path=path) for path in container.assets.list(project_id)]


@router.get("/content")
async def read_asset(
    project_id: str,
    path: str = Query(min_length=1),
    container: AppContainer = Depends(get_container),
) -> Response:
    content = container.assets.read(project_id, path)
    filename = PurePosixPath(path).name.replace('"', "")
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/content", response_model=AssetPathResponse, status_code=201)
async def create_asset(
    project_id: str,
    path: str = Query(min_length=1),
    content: bytes = Body(media_type="application/octet-stream"),
    container: AppContainer = Depends(get_container),
) -> AssetPathResponse:
    normalized = await container.assets.create(project_id, path, content)
    return AssetPathResponse(path=normalized)


@router.put("/content", response_model=AssetPathResponse)
async def save_asset(
    project_id: str,
    path: str = Query(min_length=1),
    content: bytes = Body(media_type="application/octet-stream"),
    container: AppContainer = Depends(get_container),
) -> AssetPathResponse:
    normalized = await container.assets.save(project_id, path, content)
    return AssetPathResponse(path=normalized)


@router.patch("", response_model=AssetPathResponse)
async def rename_asset(
    project_id: str,
    payload: RenameAssetRequest,
    container: AppContainer = Depends(get_container),
) -> AssetPathResponse:
    normalized = await container.assets.rename(project_id, payload.path, payload.new_path)
    return AssetPathResponse(path=normalized)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    project_id: str,
    path: str = Query(min_length=1),
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.assets.delete(project_id, path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

