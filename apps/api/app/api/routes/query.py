from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.domain.models import ChatTurn
from app.schemas.query import QueryRequest, QueryResponse
from app.services.embedding_providers import EmbeddingProviderError
from app.services.query_service import LLMProviderError, run_rag_query, run_rag_query_stream

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
)
def run_query(request: QueryRequest) -> QueryResponse:
    try:
        answer, sources = run_rag_query(
            request.query,
            top_k=request.top_k,
            history=_to_chat_history(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (EmbeddingProviderError, LLMProviderError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return QueryResponse(answer=answer, sources=sources)


@router.post("/query/stream")
async def run_query_stream(request: QueryRequest):
    
    try:
        return StreamingResponse(
            run_rag_query_stream(
                request.query,
                top_k=request.top_k,
                history=_to_chat_history(request),
            ),
            media_type="text/event-stream"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))


def _to_chat_history(request: QueryRequest) -> list[ChatTurn]:
    return [ChatTurn(role=turn.role, content=turn.content) for turn in request.history]
