from fastapi import APIRouter, HTTPException, status

from app.core.responses import not_implemented_error
from app.schemas.common import ApiError
from app.schemas.documents import (
    CompanyDocumentReplaceRequest,
    CompanyDocumentReplaceResponse,
    DocumentIngestRequest,
)
from app.services.company_documents import CompanyDocumentError, company_document_service

router = APIRouter(tags=["documents"])


@router.post(
    "/documents",
    response_model=ApiError,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def ingest_document(_: DocumentIngestRequest) -> ApiError:
    return not_implemented_error("Document ingestion")


@router.post(
    "/admin/company-document",
    response_model=CompanyDocumentReplaceResponse,
    status_code=status.HTTP_200_OK,
)
def replace_company_document(
    request: CompanyDocumentReplaceRequest,
) -> CompanyDocumentReplaceResponse:
    try:
        document = company_document_service.replace(
            request.source_name,
            request.content.encode("utf-8"),
        )
    except CompanyDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return CompanyDocumentReplaceResponse(
        message="Company document replaced",
        source_name=document.source_name,
        chunks_indexed=document.chunks_indexed,
    )
