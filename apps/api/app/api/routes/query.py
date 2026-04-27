from fastapi import APIRouter, HTTPException, status

from app.schemas.query import QueryRequest, QueryResponse
from app.services.company_documents import CompanyDocumentError, company_document_service

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
)
def run_query(request: QueryRequest) -> QueryResponse:
    try:
        results = company_document_service.search(request.query, top_k=request.top_k)
    except CompanyDocumentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    sources = [
        f"{result.metadata.get('source_name', 'company_document')}#{result.metadata.get('chunk_index', 0)}"
        for result in results
    ]
    answer = "\n\n".join(result.text for result in results)

    return QueryResponse(answer=answer, sources=sources)
