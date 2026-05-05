from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.dependencies.auth import require_admin
from app.core.responses import not_implemented_error
from app.schemas.common import ApiError
from app.schemas.documents import DocumentIngestRequest, DocumentReplaceResponse
from app.services.document_service import (
    reindex_document,
    replace_document,
    validate_filename,
    validate_size,
)

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
    # ── filename validation ───────────────────────────────────────────────
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No filename provided",
        )
    try:
        validate_filename(file.filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    # ── content validation ────────────────────────────────────────────────
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty",
        )
    try:
        validate_size(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    # ── persist + re-index ────────────────────────────────────────────────
    replace_document(file.filename, content)

    try:
        chunk_count = reindex_document(file.filename)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return DocumentReplaceResponse(
        accepted=True,
        filename=file.filename,
        message=(
            f"Document '{file.filename}' replaced and indexed successfully "
            f"({chunk_count} chunk{'s' if chunk_count != 1 else ''})."
        ),
    )