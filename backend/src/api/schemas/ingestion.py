from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IngestionMetadataIn(BaseModel):
    """Optional caller-supplied metadata for an uploaded document."""

    model_config = ConfigDict(extra="forbid")

    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    collection: str | None = Field(default=None, description="Caller-facing grouping label (not a Qdrant collection).")


class UploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    task_id: str
    status: str
    message: str


class IngestionStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    document_id: UUID
    status: str
    stage: str | None = Field(default=None, description="Pipeline stage from the persistent document status.")
    progress_percent: float | None = Field(
        default=None, description="Only populated if the worker actually reports progress; never fabricated."
    )
    error: str | None = None
