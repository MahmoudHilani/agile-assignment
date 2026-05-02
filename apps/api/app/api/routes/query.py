from fastapi import APIRouter, HTTPException, status

from app.schemas.query import QueryRequest, QueryResponse
from app.services.embedding_providers import EmbeddingProviderError
from app.services.query_service import LLMProviderError, run_rag_query

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
)
def run_query(request: QueryRequest) -> QueryResponse:
    try:
        answer, sources = run_rag_query(request.query, top_k=request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Embedding provider failed") from exc
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM provider failed") from exc

    return QueryResponse(answer=answer, sources=sources)
