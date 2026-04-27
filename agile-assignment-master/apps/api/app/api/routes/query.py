from fastapi import APIRouter, status

from app.core.responses import not_implemented_error
from app.schemas.common import ApiError
from app.schemas.query import QueryRequest

router = APIRouter(tags=["query"])


@router.post(
    "/query",
    response_model=ApiError,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
def run_query(_: QueryRequest) -> ApiError:
    return not_implemented_error("Query execution")
