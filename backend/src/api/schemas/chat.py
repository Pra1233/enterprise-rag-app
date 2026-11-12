from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: str | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    filters: ChatFilters | None = None
    stream: bool = True


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    chunk_id: UUID
    source_uri: str
    score: float


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: list[Citation]
    conversation_id: UUID | None = None
    cached: bool = False
