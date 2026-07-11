from fastapi import APIRouter, Depends, Response, status

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.projects import BotIdentityResponse
from app.api.schemas.settings import SetTokenRequest, TokenValidationResponse

router = APIRouter(prefix="/projects/{project_id}/token", tags=["settings"])


def _response(configuration) -> TokenValidationResponse:
    identity = configuration.identity
    return TokenValidationResponse(
        valid=identity is not None,
        identity=(
            BotIdentityResponse(
                bot_id=identity.bot_id,
                username=identity.username,
                display_name=identity.display_name,
            )
            if identity is not None
            else None
        ),
    )


@router.put("", response_model=TokenValidationResponse)
async def set_token(
    project_id: str,
    payload: SetTokenRequest,
    container: AppContainer = Depends(get_container),
) -> TokenValidationResponse:
    configuration = await container.settings.set_token(
        project_id,
        payload.token.get_secret_value(),
    )
    return _response(configuration)


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> TokenValidationResponse:
    return _response(await container.settings.validate_saved_token(project_id))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_token(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> Response:
    await container.settings.clear_token(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
