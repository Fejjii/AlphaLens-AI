"""High-level cache facade used by the service layer.

Wraps a ``CacheBackend`` with three responsibilities:

1. **Stable key construction.** ``build_cache_key`` hashes the JSON-canonical
   form of a payload (sorted keys, separators) so logically identical inputs
   produce identical keys regardless of dict ordering.
2. **TTL defaulting.** When a caller omits ``ttl_seconds``, the configured
   default from settings is used.
3. **Failure isolation.** Any backend exception is caught here so a broken
   cache can never break a callsite.

Cache hits are reported through structured logs (``cache_hit`` event) and via
an optional ``UsageService`` so they can be inspected via ``GET /usage/events``
without changing any response schemas.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from typing import Any

from alphalens.core.logging import get_logger
from alphalens.infrastructure.cache import CacheBackend, JSONValue

logger = get_logger(__name__)


def build_cache_key(namespace: str, payload: Any) -> str:
    """Return a deterministic cache key for *namespace* and *payload*.

    The payload is serialised with ``json.dumps(..., sort_keys=True)`` and
    hashed with SHA-256. The full key looks like ``alphalens:{namespace}:{hash}``.
    Strings, numbers, lists, tuples, and (nested) dicts of those are supported.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"alphalens:{namespace}:{digest}"


class CacheService:
    """Service-layer cache facade with safe defaults."""

    def __init__(
        self,
        *,
        backend: CacheBackend,
        default_ttl_seconds: int,
        enabled: bool = True,
        usage_service: object | None = None,
    ) -> None:
        self._backend = backend
        self._default_ttl = default_ttl_seconds
        self._enabled = enabled
        self._usage = usage_service

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_cached(self, key: str) -> JSONValue:
        if not self._enabled:
            return None
        try:
            value = self._backend.get_json(key)
        except Exception as exc:
            logger.warning("cache_get_failed", key=key, error=str(exc))
            return None
        if value is not None:
            self._record_hit(key)
        return value

    def set_cached(
        self,
        key: str,
        value: JSONValue,
        ttl_seconds: int | None = None,
    ) -> None:
        if not self._enabled:
            return
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        try:
            self._backend.set_json(key, value, ttl_seconds=ttl)
        except Exception as exc:
            logger.warning("cache_set_failed", key=key, error=str(exc))

    def delete(self, key: str) -> None:
        if not self._enabled:
            return
        try:
            self._backend.delete(key)
        except Exception as exc:
            logger.warning("cache_delete_failed", key=key, error=str(exc))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_hit(self, key: str) -> None:
        # Namespace is the second segment of the key: alphalens:<namespace>:<hash>
        namespace = key.split(":", 2)[1] if key.count(":") >= 2 else "unknown"
        logger.info("cache_hit", namespace=namespace)
        if self._usage is None:
            return
        # Never let usage tracking break cache reads.
        with contextlib.suppress(Exception):
            self._usage.record_llm_usage(  # type: ignore[attr-defined]
                event_type="cache_hit",
                provider="cache",
                model=None,
                metadata={"namespace": namespace},
            )
