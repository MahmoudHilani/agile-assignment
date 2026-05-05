from fastapi import APIRouter, status

from app.core.responses import not_implemented_error
from app.schemas.common import ApiError
from app.schemas.documents import DocumentIngestRequest

router = APIRouter(tags=["documents"])


@router.post(
    "/documents",
    response_model=ApiError,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def ingest_document(_: DocumentIngestRequest) -> ApiError:
    return not_implemented_error("Document ingestion")
