from fastapi import APIRouter

from app.api.routes import auth, documents, health, query, voice, tts_routes

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(query.router)
api_router.include_router(voice.router)
api_router.include_router(tts_routes.router)