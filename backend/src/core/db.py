import uuid
from collections.abc import Generator
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from src.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.postgres_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class DocumentRecord(Base):
    """Persistent record of an ingested document's metadata, ownership and pipeline status."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Ownership / multi-tenancy — every row MUST carry a tenant_id, set server-side
    # from the verified JWT, never from a client-supplied field.
    tenant_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    source_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)

    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False, doc="Object key in MinIO.")

    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    parent_chunks: Mapped[list["ParentChunkRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ParentChunkRecord(Base):
    """Persistent record of a 'big' parent chunk, fetched by ID after child-chunk retrieval."""

    __tablename__ = "parent_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_numbers: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document: Mapped["DocumentRecord"] = relationship(back_populates="parent_chunks")


class User(Base):
    """A login account: credentials, role, and lifetime usage quotas."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # Plain string rather than a DB enum (same choice as DocumentRecord.status);
    # validated as Literal["admin", "user"] at the Pydantic schema layer.
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")

    llm_request_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    llm_requests_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    upload_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    uploads_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    login_events: Mapped[list["LoginAuditLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class LoginAuditLog(Base):
    """One row per successful login — who, when, and from where."""

    __tablename__ = "login_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Snapshot at login time, kept alongside the FK so this table still reads
    # correctly on its own (e.g. in a raw SQL report) without a join.
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    logged_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    user: Mapped["User"] = relationship(back_populates="login_events")


def get_db() -> Generator[Session]:
    """FastAPI dependency yielding a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
