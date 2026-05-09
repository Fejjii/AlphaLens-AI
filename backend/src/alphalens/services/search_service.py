"""Search service: provider selection, caching, and graceful fallback.

Selection rule:

    if SEARCH_PROVIDER == "serper" and SERPER_API_KEY
        -> SerperSearchClient
    else
        -> FallbackSearchClient

When the primary client raises `SearchError` we log the failure and fall
through to the deterministic client so the agent never crashes on
upstream issues.
"""

from __future__ import annotations

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger
from alphalens.integrations.search import (
    FallbackSearchClient,
    SearchClient,
    SearchError,
    SerperSearchClient,
)
from alphalens.schemas.search import SearchResponse
from alphalens.services.cache_service import CacheService, build_cache_key

logger = get_logger(__name__)

DEFAULT_K = 5
_NAMESPACE = "search"


class SearchService:
    """Wraps a primary client and a deterministic fallback."""

    def __init__(
        self,
        *,
        primary: SearchClient | None,
        fallback: SearchClient,
        cache: CacheService | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._cache = cache

    @property
    def using_external(self) -> bool:
        """True when an external provider is configured."""
        return self._primary is not None

    def search(self, query: str, k: int = DEFAULT_K) -> SearchResponse:
        cached = self._get_cached(query, k)
        if cached is not None:
            return cached
        response = self._do_search(query, k)
        self._set_cached(query, k, response)
        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _do_search(self, query: str, k: int) -> SearchResponse:
        if self._primary is None:
            response = self._fallback.search(query, k=k)
            return response.model_copy(
                update={"fallback_used": True, "provider_source": "fallback_default"}
            )
        try:
            response = self._primary.search(query, k=k)
            return response.model_copy(
                update={"fallback_used": False, "provider_source": "primary"}
            )
        except SearchError as exc:
            logger.warning(
                "search_fallback",
                query=query,
                error=str(exc),
                reason="primary_error",
            )
            response = self._fallback.search(query, k=k)
            return response.model_copy(
                update={"fallback_used": True, "provider_source": "fallback_on_error"}
            )

    def _cache_key(self, query: str, k: int) -> str:
        return build_cache_key(_NAMESPACE, {"q": query.strip().lower(), "k": k})

    def _get_cached(self, query: str, k: int) -> SearchResponse | None:
        if self._cache is None:
            return None
        key = self._cache_key(query, k)
        raw = self._cache.get_cached(key)
        if raw is None:
            return None
        try:
            return SearchResponse.model_validate(raw)
        except Exception as exc:
            logger.warning("cache_decode_failed", namespace=_NAMESPACE, error=str(exc))
            self._cache.delete(key)
            return None

    def _set_cached(self, query: str, k: int, response: SearchResponse) -> None:
        if self._cache is None:
            return
        key = self._cache_key(query, k)
        self._cache.set_cached(key, response.model_dump(mode="json"))


def resolve_search_provider(settings: Settings) -> tuple[str, bool]:
    """Return effective search provider and whether external is enabled.

    The runtime auto-enables Serper when an API key is present, even if
    SEARCH_PROVIDER is left at its historical fallback default.
    """
    if settings.serper_api_key:
        return ("serper", True)
    return ("fallback", False)


def get_search_client(settings: Settings) -> SearchClient | None:
    """Build the primary client, or None when external provider is disabled."""
    provider, using_external = resolve_search_provider(settings)
    if provider == "serper" and using_external:
        try:
            return SerperSearchClient(
                api_key=settings.serper_api_key,
                timeout_seconds=settings.search_timeout_seconds,
            )
        except SearchError as exc:
            logger.warning("search_client_init_failed", error=str(exc))
            return None
    return None


def get_search_service(
    settings: Settings,
    *,
    cache: CacheService | None = None,
) -> SearchService:
    return SearchService(
        primary=get_search_client(settings),
        fallback=FallbackSearchClient(),
        cache=cache,
    )
