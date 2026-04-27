from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api import router
from app.document_service import initialize_company_document


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_company_document()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(router)