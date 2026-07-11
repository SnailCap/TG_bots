from fastapi import APIRouter

from app.api.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", schema_version=1, api_version="v1")

