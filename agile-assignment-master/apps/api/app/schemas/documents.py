from typing import Any

from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    source_name: str
    content_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentIngestResponse(BaseModel):
    accepted: bool
    message: str
