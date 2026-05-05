from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    application = FastAPI(
        title=resolved_settings.app_name,
        debug=resolved_settings.app_env == "development",
    )
    application.include_router(api_router)
    return application


app = create_app()
