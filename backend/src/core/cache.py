import hashlib
import json
import logging
import re
from functools import lru_cache
from typing import Any

import redis

from src.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_redis_client() -> redis.Redis:
    """Cached, process-wide Redis connection (decoded responses, used for caching)."""
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


class RedisCache:
    """Thin JSON-serializing cache wrapper around a Redis connection.

    Used for non-critical caching (e.g. query results, reranker scores) where
    a cache miss or Redis outage should degrade gracefully, never raise.
    """

    def __init__(self, namespace: str, default_ttl_seconds: int = 3600) -> None:
        self._client = get_redis_client()
        self._namespace = namespace
        self._default_ttl_seconds = default_ttl_seconds

    def _key(self, key: str) -> str:
        return f"{self._namespace}:{key}"

    def get(self, key: str) -> Any | None:
        try:
            raw = self._client.get(self._key(key))
        except redis.RedisError:
            logger.warning("Redis GET failed for key=%s; treating as cache miss", key, exc_info=True)
            return None
        return json.loads(raw) if raw is not None else None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        try:
            self._client.set(self._key(key), json.dumps(value), ex=ttl_seconds or self._default_ttl_seconds)
        except redis.RedisError:
            logger.warning("Redis SET failed for key=%s; continuing without cache", key, exc_info=True)

    def delete(self, key: str) -> None:
        try:
            self._client.delete(self._key(key))
        except redis.RedisError:
            logger.warning("Redis DELETE failed for key=%s", key, exc_info=True)


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Canonicalize a query string so trivially-different inputs ('What is X?'
    vs '  what is x? ') hit the same cache key.
    """
    return _WHITESPACE_RE.sub(" ", query.strip().lower())


class ChatResponseCache:
    """Exact-match cache for chat responses.

    The cache key folds in everything that could change the correct answer
    for the same literal question: the tenant, the caller's access scope,
    any retrieval filters, and a per-tenant document version counter that is
    bumped on every ingest/delete/reprocess — so stale answers are never
    served after the knowledge base changes, without having to enumerate and
    delete individual cache entries.

    Deliberately exact-hash only (no embedding similarity) — see note in
    `get_semantic` for how this would extend to semantic caching later.
    """

    NAMESPACE = "chat_cache"
    VERSION_NAMESPACE = "chat_cache_doc_version"

    def __init__(self, default_ttl_seconds: int) -> None:
        self._cache = RedisCache(namespace=self.NAMESPACE, default_ttl_seconds=default_ttl_seconds)
        self._version_cache = RedisCache(namespace=self.VERSION_NAMESPACE, default_ttl_seconds=0)
        self._client = get_redis_client()

    def _document_version(self, tenant_id: str) -> int:
        try:
            raw = self._client.get(f"{self.VERSION_NAMESPACE}:{tenant_id}")
        except redis.RedisError:
            logger.warning("Redis GET failed reading doc version for tenant=%s", tenant_id, exc_info=True)
            return 0
        return int(raw) if raw is not None else 0

    def bump_document_version(self, tenant_id: str) -> None:
        """Call this on any document create/delete/reprocess for a tenant.
        Invalidates every previously cached response for that tenant in O(1),
        without needing to track or scan individual cache keys.
        """
        try:
            self._client.incr(f"{self.VERSION_NAMESPACE}:{tenant_id}")
        except redis.RedisError:
            logger.warning("Redis INCR failed bumping doc version for tenant=%s", tenant_id, exc_info=True)

    def _build_key(self, *, tenant_id: str, user_scope: list[str], query: str, filters: dict[str, Any]) -> str:
        doc_version = self._document_version(tenant_id)
        payload = {
            "tenant_id": tenant_id,
            "user_scope": sorted(user_scope),
            "query": normalize_query(query),
            "filters": {k: filters[k] for k in sorted(filters)},
            "doc_version": doc_version,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        return digest

    def get(
        self, *, tenant_id: str, user_scope: list[str], query: str, filters: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        key = self._build_key(tenant_id=tenant_id, user_scope=user_scope, query=query, filters=filters or {})
        return self._cache.get(key)

    def set(
        self,
        *,
        tenant_id: str,
        user_scope: list[str],
        query: str,
        answer: str,
        citations: list[dict[str, Any]],
        filters: dict[str, Any] | None = None,
    ) -> None:
        key = self._build_key(tenant_id=tenant_id, user_scope=user_scope, query=query, filters=filters or {})
        self._cache.set(key, {"answer": answer, "citations": citations})

    def get_semantic(self, **kwargs: Any) -> dict[str, Any] | None:
        """Extension point for semantic (embedding-similarity) caching.

        Not implemented: this cache is exact-hash only by design. A future
        implementation would embed the query, search a small vector index of
        past (query, tenant, scope) -> answer pairs, and fall back to this
        exact-match cache on a miss.
        """
        raise NotImplementedError("Semantic caching is not implemented; use get() for exact-match lookups.")
