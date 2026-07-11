from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.container import AppContainer
from app.api.dependencies import get_container
from app.api.schemas.runtime import (
    RuntimeLogResponse,
    RuntimeStatusResponse,
    runtime_log_response,
    runtime_status_response,
)
from app.errors import RuntimeOperationError, StudioError, TokenValidationError, ValidationFailedError
from app.runtime.errors import RuntimeValidationError

router = APIRouter(prefix="/projects/{project_id}/runtime", tags=["runtime"])


@router.get("/status", response_model=RuntimeStatusResponse)
async def runtime_status(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> RuntimeStatusResponse:
    container.projects.get(project_id)
    return runtime_status_response(container.runtime_manager.status(project_id))


@router.post("/run", response_model=RuntimeStatusResponse)
async def run_runtime(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> RuntimeStatusResponse:
    opened = container.projects.get(project_id)
    reference = opened.project.configuration.secret_ref
    if reference is None:
        raise TokenValidationError("Telegram token is not configured")
    token = container.secret_store.get(reference)
    if token is None:
        raise TokenValidationError(
            "Telegram token reference exists, but the secret is unavailable"
        )
    try:
        status = await container.runtime_manager.run(
            opened.project,
            opened.path,
            token,
        )
    except RuntimeValidationError as exc:
        raise ValidationFailedError(str(exc)) from exc
    except StudioError:
        raise
    except Exception as exc:
        raise RuntimeOperationError(f"Cannot start bot runtime: {exc}") from exc
    return runtime_status_response(status)


@router.post("/stop", response_model=RuntimeStatusResponse)
async def stop_runtime(
    project_id: str,
    container: AppContainer = Depends(get_container),
) -> RuntimeStatusResponse:
    container.projects.get(project_id)
    try:
        status = await container.runtime_manager.stop(project_id)
    except StudioError:
        raise
    except Exception as exc:
        raise RuntimeOperationError(f"Cannot stop bot runtime: {exc}") from exc
    return runtime_status_response(status)


@router.get("/logs", response_model=list[RuntimeLogResponse])
async def runtime_logs(
    project_id: str,
    session_id: str | None = None,
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=200, ge=1, le=2_000),
    container: AppContainer = Depends(get_container),
) -> list[RuntimeLogResponse]:
    opened = container.projects.get(project_id)
    storage = container.runtime_storage_factory(opened.path)
    return [
        runtime_log_response(item)
        for item in storage.list_history(
            project_id,
            session_id=session_id,
            after_id=after_id,
            limit=limit,
        )
    ]
