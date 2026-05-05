from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.services.document_service import initialize_document_index


def _parse_cors_origins(cors_origins: str) -> list[str]:
    return [origin.strip() for origin in cors_origins.split(",") if origin.strip()]


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        initialize_document_index(resolved_settings)
        yield

    application = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.app_env == "development",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_cors_origins(resolved_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()
