from fastapi import APIRouter, Depends

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.scripts import issue_response
from app.api.schemas.validation import ValidationResponse

router = APIRouter(prefix="/projects/{project_id}/validation", tags=["validation"])


@router.post("", response_model=ValidationResponse)
async def validate_project(
    project_id: str,
    validate_imports: bool = True,
    container: AppContainer = Depends(get_container),
) -> ValidationResponse:
    report = container.validation.validate(
        project_id,
        validate_imports=validate_imports,
    )
    return ValidationResponse(
        valid=report.valid,
        issues=[issue_response(issue) for issue in report.issues],
    )


alias_router = APIRouter(prefix="/projects/{project_id}/validate", tags=["validation"])


@alias_router.post("", response_model=ValidationResponse)
async def validate_project_alias(
    project_id: str,
    validate_imports: bool = True,
    container: AppContainer = Depends(get_container),
) -> ValidationResponse:
    return await validate_project(project_id, validate_imports, container)
