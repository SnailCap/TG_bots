from fastapi import APIRouter, Depends, Response, status

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.projects import BotConfigurationResponse, configuration_response
from app.api.schemas.settings import PatchSettingsRequest, SetTokenRequest

router = APIRouter(prefix="/projects/{project_id}/settings", tags=["settings"])


@router.get("", response_model=BotConfigurationResponse)
async def get_settings(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> BotConfigurationResponse:
    return configuration_response(container.settings.get(project_id))


@router.patch("", response_model=BotConfigurationResponse)
@router.put("", response_model=BotConfigurationResponse)
async def patch_settings(
    project_id: str,
    payload: PatchSettingsRequest,
    container: AppContainer = Depends(get_container),
) -> BotConfigurationResponse:
    current = container.settings.get(project_id)
    start_flow_id = (
        payload.start_flow_id
        if "start_flow_id" in payload.model_fields_set
        else current.start_flow_id
    )
    configuration = await container.settings.update(
        project_id,
        start_flow_id=start_flow_id,
        start_behavior=payload.start_behavior,
    )
    return configuration_response(configuration)


@router.put("/token", response_model=BotConfigurationResponse)
async def set_token(
    project_id: str,
    payload: SetTokenRequest,
    container: AppContainer = Depends(get_container),
) -> BotConfigurationResponse:
    configuration = await container.settings.set_token(
        project_id,
        payload.token.get_secret_value(),
    )
    return configuration_response(configuration)


@router.delete("/token", status_code=status.HTTP_204_NO_CONTENT)
async def clear_token(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.settings.clear_token(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
