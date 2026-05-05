from typing import Literal

from pydantic import BaseModel, Field


MAX_QUERY_LENGTH = 1000
MAX_HISTORY_MESSAGES = 12
MAX_HISTORY_CONTENT_LENGTH = 2000


class QueryChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_HISTORY_CONTENT_LENGTH)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)
    top_k: int = Field(default=5, ge=1, le=25)
    history: list[QueryChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)


class QueryResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
