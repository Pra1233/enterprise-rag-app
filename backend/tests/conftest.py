import os
import tempfile
import uuid
from pathlib import Path

import jwt
import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="rag_test_")
_DB_PATH = Path(_TMP_DIR) / "test.db"

# Must be set BEFORE anything imports src.core.config (get_settings is lru_cached
# and pydantic-settings reads these at Settings() construction time).
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-at-least-32-bytes-long")
os.environ.setdefault("POSTGRES_URL", f"sqlite:///{_DB_PATH}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("CACHE_ENABLED", "true")
os.environ.setdefault("LANGSMITH_TRACING", "false")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import app  # noqa: E402
from src.core.db import Base, DocumentRecord, SessionLocal, User, engine  # noqa: E402
from src.core.security import hash_password  # noqa: E402

# Deterministic UUIDs for the handful of named test identities used throughout
# the suite. "tenant-1"/"user-1" map to the SAME id because the auth model is
# one-tenant-per-user: a request's tenant_id is always its own user id, never
# an independently-assigned value. Keeping the old string names as fixture
# arguments (rather than touching every call site) means existing tests read
# unchanged; only this lookup table encodes the new tenant===user reality.
_IDENTITY_IDS = {
    "user-1": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "tenant-1": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "user-2": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    "user-3": uuid.UUID("33333333-3333-3333-3333-333333333333"),
    "tenant-2": uuid.UUID("33333333-3333-3333-3333-333333333333"),
}


def _resolve_identity(name: str) -> uuid.UUID:
    return _IDENTITY_IDS.get(name, uuid.uuid5(uuid.NAMESPACE_DNS, name))


def _ensure_user(user_id: uuid.UUID, username: str) -> None:
    with SessionLocal() as db:
        if db.get(User, user_id) is None:
            db.add(
                User(
                    id=user_id,
                    username=username,
                    hashed_password=hash_password("test-password"),
                    role="user",
                )
            )
            db.commit()


class FakeRedis:
    """Minimal in-memory stand-in for redis.Redis (decode_responses=True)."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)

    def incr(self, key):
        self.store[key] = str(int(self.store.get(key, 0)) + 1)
        return int(self.store[key])


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Every test gets a fresh fake Redis — chat cache and doc-version counters
    reset between tests, matching how a real Redis TTL cache behaves in isolation.
    """
    shared = FakeRedis()
    monkeypatch.setattr("src.core.cache.get_redis_client", lambda: shared)
    return shared


@pytest.fixture(autouse=True)
def _clean_documents_table():
    yield
    with SessionLocal() as db:
        db.query(DocumentRecord).delete()
        db.commit()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


def make_token(tenant_id: str = "tenant-1", user_id: str = "user-1", scopes: list[str] | None = None) -> str:
    """Mint a token for a named test identity, creating its backing User row
    if needed. `tenant_id`/`scopes` claims are accepted for call-site
    compatibility but are no longer trusted by get_current_principal — only
    `sub` (resolved to a real User row) matters now.
    """
    real_user_id = _resolve_identity(user_id)
    _ensure_user(real_user_id, username=user_id)
    settings_secret = os.environ["JWT_SECRET_KEY"]
    return jwt.encode(
        {"sub": str(real_user_id), "tenant_id": tenant_id, "scopes": scopes or []},
        settings_secret,
        algorithm="HS256",
    )


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {make_token(tenant_id='tenant-1', user_id='user-1')}"}


@pytest.fixture
def other_user_headers():
    """Same tenant, different user — no admin scope."""
    return {"Authorization": f"Bearer {make_token(tenant_id='tenant-1', user_id='user-2')}"}


@pytest.fixture
def other_tenant_headers():
    return {"Authorization": f"Bearer {make_token(tenant_id='tenant-2', user_id='user-3')}"}


def make_document_record(tenant_id: str = "tenant-1", owner_id: str = "user-1", **overrides) -> DocumentRecord:
    # tenant_id/owner_id on a request are always the caller's own user id now
    # (see _IDENTITY_IDS above) — resolve the same logical names to the same
    # real UUIDs so a document "in tenant-1" is actually visible to a
    # principal minted via make_token(user_id="user-1").
    resolved_tenant_id = str(_resolve_identity(tenant_id))
    resolved_owner_id = str(_resolve_identity(owner_id))
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=resolved_tenant_id,
        owner_id=resolved_owner_id,
        source_uri=f"{tenant_id}/doc.pdf",
        document_type="pdf",
        author=None,
        original_filename="doc.pdf",
        file_size_bytes=1024,
        content_hash="a" * 64,
        storage_path=f"{tenant_id}/doc.pdf",
        status="indexed",
    )
    defaults.update(overrides)
    record = DocumentRecord(**defaults)
    with SessionLocal() as db:
        db.add(record)
        db.commit()
        db.refresh(record)
    return record
