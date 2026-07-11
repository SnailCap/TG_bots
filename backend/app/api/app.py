from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .container import AppContainer, create_default_container
from .error_handlers import install_error_handlers
from .routers import ALL_ROUTERS


def create_app(container: AppContainer | None = None) -> FastAPI:
    selected_container = container or create_default_container()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await selected_container.runtime_manager.stop_all()

    application = FastAPI(
        title="Telegram Bot Studio API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.state.container = selected_container
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["null"],
        allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(application)
    for router in ALL_ROUTERS:
        application.include_router(router, prefix="/api/v1")
    return application


app = create_app()
