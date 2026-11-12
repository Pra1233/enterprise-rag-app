"""Open Knowledge Format (OKF): strict Pydantic V2 models shared across the
ingestion and retrieval pipelines. No loose dicts are passed between stages —
every unit of data crossing a boundary is one of these models.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class OKFBaseModel(BaseModel):
    """Base for all OKF objects: unknown fields are rejected, assignments validated."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"


class DocumentMetadata(OKFBaseModel):
    """Source-level metadata for a single ingested document."""

    document_id: UUID = Field(default_factory=uuid4)
    tenant_id: str = Field(..., min_length=1, description="Owning tenant; enforced in every Qdrant query.")
    source_uri: str = Field(..., min_length=1, description="Path or URL the document was ingested from.")
    document_type: DocumentType
    author: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    page_numbers: list[int] = Field(default_factory=list, description="Page numbers the document spans.")


class ParentChunk(OKFBaseModel):
    """A 'big' chunk (~1024 tokens) kept in Postgres and fetched for LLM context
    once one of its child chunks is retrieved from the vector store.
    """

    parent_id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int = Field(..., ge=0)
    content: str = Field(..., min_length=1)
    token_count: int = Field(..., ge=0)
    page_numbers: list[int] = Field(default_factory=list)


class KnowledgeChunk(OKFBaseModel):
    """A 'small' child chunk (~256 tokens): the atomic unit that gets embedded
    and indexed in Qdrant for precise similarity search.
    """

    chunk_id: UUID = Field(default_factory=uuid4)
    parent_doc_id: UUID = Field(..., description="ID of the ParentChunk providing LLM-context on retrieval.")
    content: str = Field(..., min_length=1)
    dense_embedding: list[float] | None = Field(
        default=None, description="Dense vector from BAAI/bge-small-en-v1.5 (384-dim)."
    )
    sparse_embedding: dict[int, float] | None = Field(
        default=None, description="Optional sparse vector {token_index: weight} for hybrid search."
    )
    metadata: DocumentMetadata


class RetrievedChunk(OKFBaseModel):
    """A chunk as returned from Qdrant search + reranking, flattened for the RAG graph."""

    chunk_id: UUID
    parent_doc_id: UUID
    content: str
    document_id: UUID
    tenant_id: str
    source_uri: str
    document_type: DocumentType
    author: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    score: float
    rerank_score: float | None = None
