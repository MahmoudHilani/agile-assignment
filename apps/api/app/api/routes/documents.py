from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from app.api.dependencies.auth import require_admin
from app.core.responses import not_implemented_error
from app.schemas.common import ApiError
from app.schemas.documents import DocumentIngestRequest, DocumentReplaceResponse, PdfParseResponse
from app.services.document_service import replace_document, validate_filename, validate_size, parse_document
from app.services.embedding_providers import EmbeddingProviderError

router = APIRouter(tags=["documents"])

@router.post(
    "/documents",
    response_model=ApiError,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def ingest_document(_: DocumentIngestRequest) -> ApiError:
    return not_implemented_error("Document ingestion")

@router.put("/documents", response_model=DocumentReplaceResponse)
async def replace_document_endpoint(
    file: UploadFile = File(...),
    _admin: dict = Depends(require_admin),
) -> DocumentReplaceResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No filename provided")
    try:
        validate_filename(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")
    try:
        validate_size(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    try:
        replace_document(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Embedding provider failed") from exc
    return DocumentReplaceResponse(
        accepted=True,
        filename=file.filename,
        message=f"Document '{file.filename}' replaced successfully",
    )

@router.post("/documents/parse-pdf", response_model=PdfParseResponse)
async def parse_pdf_endpoint(file: UploadFile = File(...)) -> PdfParseResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only PDF files are supported")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")
    try:
        validate_size(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    try:
        text = parse_document(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return PdfParseResponse(
        filename=file.filename,
        extracted_text=text,
        page_count=None,
        mime_type="application/pdf",
    )
