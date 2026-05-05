from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str
    conversation_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=25)


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
