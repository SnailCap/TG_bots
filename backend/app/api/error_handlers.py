from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import StudioError


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StudioError)
    async def handle_studio_error(request: Request, exc: StudioError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": str(exc),
                    "details": {},
                }
            },
        )

