from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.git import router as git_router
from app.api.routers.health import router as health_router
from app.api.routers.projects import router as projects_router
from app.integrations.git import GitService
from app.workspace import ProjectService


def create_app() -> FastAPI:
    app = FastAPI(
        title="Telegram Bot Studio API",
        version="3.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "null",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.state.project_service = ProjectService()
    app.state.git_service = GitService(
        app.state.project_service.repository,
        app.state.project_service.validate,
    )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    app.include_router(git_router, prefix="/api/v1")
    return app


app = create_app()
