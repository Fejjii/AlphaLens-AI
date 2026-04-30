"""Tests for the Redis/in-memory cache infrastructure and per-service caching.

The per-service tests use ``MagicMock`` clients so we can assert exactly how
many times the underlying provider is invoked. The first call should hit the
provider; the second call (with identical args) should be served from cache.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from alphalens.core.config import Settings
from alphalens.infrastructure.cache import (
    InMemoryCacheBackend,
    RedisCacheBackend,
    build_cache_backend,
)
from alphalens.integrations.macro.base import MacroDataError
from alphalens.integrations.macro.fallback_client import FallbackMacroClient
from alphalens.integrations.market_data import DeterministicFallbackMarketDataClient
from alphalens.integrations.search import FallbackSearchClient
from alphalens.integrations.sec.base import SECError
from alphalens.integrations.sec.fallback_client import FallbackSECClient
from alphalens.services.cache_service import CacheService, build_cache_key
from alphalens.services.macro_service import MacroService
from alphalens.services.market_data_service import MarketDataService
from alphalens.services.search_service import SearchService
from alphalens.services.sec_service import SECService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cache(enabled: bool = True, ttl: int = 300) -> CacheService:
    return CacheService(
        backend=InMemoryCacheBackend(),
        default_ttl_seconds=ttl,
        enabled=enabled,
    )


# ---------------------------------------------------------------------------
# 1. Cache key construction is stable
# ---------------------------------------------------------------------------


def test_build_cache_key_is_stable_for_same_payload() -> None:
    a = build_cache_key("market_data", {"ticker": "AAPL", "k": 5})
    b = build_cache_key("market_data", {"k": 5, "ticker": "AAPL"})  # different order
    assert a == b


def test_build_cache_key_differs_per_namespace() -> None:
    a = build_cache_key("market_data", {"ticker": "AAPL"})
    b = build_cache_key("search", {"ticker": "AAPL"})
    assert a != b


def test_build_cache_key_differs_per_payload() -> None:
    a = build_cache_key("market_data", {"ticker": "AAPL"})
    b = build_cache_key("market_data", {"ticker": "MSFT"})
    assert a != b


# ---------------------------------------------------------------------------
# 2. In-memory backend get/set/delete + TTL
# ---------------------------------------------------------------------------


def test_in_memory_get_set_delete() -> None:
    backend = InMemoryCacheBackend()
    backend.set_json("k", {"hello": "world"})
    assert backend.get_json("k") == {"hello": "world"}

    backend.delete("k")
    assert backend.get_json("k") is None


def test_in_memory_ttl_expires() -> None:
    backend = InMemoryCacheBackend()
    backend.set_json("k", "v", ttl_seconds=1)
    assert backend.get_json("k") == "v"
    time.sleep(1.05)
    assert backend.get_json("k") is None


def test_in_memory_unknown_key_returns_none() -> None:
    assert InMemoryCacheBackend().get_json("missing") is None


# ---------------------------------------------------------------------------
# 3. CacheService respects enabled flag and default TTL
# ---------------------------------------------------------------------------


def test_cache_service_disabled_is_passthrough() -> None:
    service = _make_cache(enabled=False)
    service.set_cached("k", "v")
    assert service.get_cached("k") is None


def test_cache_service_default_ttl_used_when_omitted() -> None:
    backend = InMemoryCacheBackend()
    service = CacheService(backend=backend, default_ttl_seconds=1)
    service.set_cached("k", "v")
    assert backend.get_json("k") == "v"
    time.sleep(1.05)
    assert backend.get_json("k") is None


# ---------------------------------------------------------------------------
# 4. Service-layer: market data
# ---------------------------------------------------------------------------


def test_cached_market_quote_avoids_second_provider_call() -> None:
    real = DeterministicFallbackMarketDataClient()
    spy = MagicMock(wraps=real)
    cache = _make_cache()
    service = MarketDataService(primary=None, fallback=spy, cache=cache)

    q1 = service.get_quote("NVDA")
    q2 = service.get_quote("NVDA")

    assert q1 == q2
    assert spy.get_quote.call_count == 1, "second call must be served from cache"


def test_market_quote_cache_disabled_calls_provider_each_time() -> None:
    real = DeterministicFallbackMarketDataClient()
    spy = MagicMock(wraps=real)
    service = MarketDataService(primary=None, fallback=spy, cache=None)

    service.get_quote("NVDA")
    service.get_quote("NVDA")
    assert spy.get_quote.call_count == 2


def test_market_quote_provider_failure_does_not_crash_when_cache_broken() -> None:
    """Even if the cache layer raises, the service must return a quote."""

    class _BadCache:
        def get_json(self, key):
            raise RuntimeError("redis exploded")

        def set_json(self, key, value, ttl_seconds=None):
            raise RuntimeError("redis exploded")

        def delete(self, key):
            raise RuntimeError("redis exploded")

    cache = CacheService(backend=_BadCache(), default_ttl_seconds=300)
    service = MarketDataService(
        primary=None,
        fallback=DeterministicFallbackMarketDataClient(),
        cache=cache,
    )
    quote = service.get_quote("NVDA")
    assert quote.ticker == "NVDA"


# ---------------------------------------------------------------------------
# 5. Service-layer: search
# ---------------------------------------------------------------------------


def test_cached_search_avoids_second_provider_call() -> None:
    real = FallbackSearchClient()
    spy = MagicMock(wraps=real)
    cache = _make_cache()
    service = SearchService(primary=None, fallback=spy, cache=cache)

    r1 = service.search("inflation outlook")
    r2 = service.search("inflation outlook")

    assert r1 == r2
    assert spy.search.call_count == 1


def test_search_cache_key_differs_for_different_k() -> None:
    real = FallbackSearchClient()
    spy = MagicMock(wraps=real)
    cache = _make_cache()
    service = SearchService(primary=None, fallback=spy, cache=cache)

    service.search("rates", k=3)
    service.search("rates", k=5)
    assert spy.search.call_count == 2


# ---------------------------------------------------------------------------
# 6. Service-layer: macro
# ---------------------------------------------------------------------------


def _macro_service(client, cache: CacheService | None) -> MacroService:
    """Build a MacroService bypassing __init__ (avoids settings dependency)."""
    service = MacroService.__new__(MacroService)
    service._primary = client
    service._fallback = FallbackMacroClient()
    service._cache = cache
    return service


def test_cached_macro_snapshot_avoids_second_provider_call() -> None:
    real = FallbackMacroClient()
    spy = MagicMock(wraps=real)
    service = _macro_service(spy, _make_cache())

    s1 = service.get_macro_snapshot()
    s2 = service.get_macro_snapshot()

    assert s1 == s2
    assert spy.get_macro_snapshot.call_count == 1


def test_cached_macro_series_avoids_second_provider_call() -> None:
    real = FallbackMacroClient()
    spy = MagicMock(wraps=real)
    service = _macro_service(spy, _make_cache())

    service.get_series("FEDFUNDS", limit=3)
    service.get_series("FEDFUNDS", limit=3)
    assert spy.get_series.call_count == 1


def test_macro_cache_does_not_mask_fallback_on_provider_error() -> None:
    failing = MagicMock()
    failing.get_macro_snapshot.side_effect = MacroDataError("provider down")
    service = _macro_service(failing, _make_cache())

    snapshot = service.get_macro_snapshot()
    assert snapshot.observations  # fallback returned realistic data


# ---------------------------------------------------------------------------
# 7. Service-layer: SEC
# ---------------------------------------------------------------------------


def _sec_service(client, cache: CacheService | None) -> SECService:
    service = SECService.__new__(SECService)
    service._primary = client
    service._fallback = FallbackSECClient()
    service._cache = cache
    return service


def test_cached_sec_filings_avoid_second_provider_call() -> None:
    real = FallbackSECClient()
    spy = MagicMock(wraps=real)
    service = _sec_service(spy, _make_cache())

    service.get_recent_filings("NVDA", limit=2)
    service.get_recent_filings("NVDA", limit=2)
    assert spy.get_recent_filings.call_count == 1


def test_cached_sec_sections_avoid_second_provider_call() -> None:
    real = FallbackSECClient()
    spy = MagicMock(wraps=real)
    service = _sec_service(spy, _make_cache())

    s1 = service.get_filing_sections("NVDA", form_type="10-K")
    s2 = service.get_filing_sections("NVDA", form_type="10-K")

    assert s1 == s2
    assert spy.get_filing_sections.call_count == 1


def test_sec_cache_does_not_mask_fallback_on_provider_error() -> None:
    failing = MagicMock()
    failing.get_filing_sections.side_effect = SECError("EDGAR down")
    service = _sec_service(failing, _make_cache())

    sections = service.get_filing_sections("NVDA", form_type="10-K")
    assert sections, "fallback sections must be returned"


# ---------------------------------------------------------------------------
# 8. App works when cache is disabled (settings flag)
# ---------------------------------------------------------------------------


def test_build_cache_backend_when_disabled_uses_in_memory() -> None:
    settings = Settings(CACHE_ENABLED=False, REDIS_URL="redis://localhost:6379/0")
    backend = build_cache_backend(settings)
    assert isinstance(backend, InMemoryCacheBackend)


def test_build_cache_backend_without_redis_url_uses_in_memory() -> None:
    settings = Settings(CACHE_ENABLED=True, REDIS_URL=None)
    backend = build_cache_backend(settings)
    assert isinstance(backend, InMemoryCacheBackend)


def test_build_cache_backend_falls_back_when_redis_unreachable() -> None:
    """Pointing at a closed port must not raise; we get the in-memory backend."""
    settings = Settings(
        CACHE_ENABLED=True,
        REDIS_URL="redis://127.0.0.1:65500/0",  # almost-certainly closed port
    )
    backend = build_cache_backend(settings)
    assert isinstance(backend, InMemoryCacheBackend)


# ---------------------------------------------------------------------------
# 9. Redis backend failure does not crash the service
# ---------------------------------------------------------------------------


def test_redis_backend_get_swallows_client_failure() -> None:
    fake_client = MagicMock()
    fake_client.get.side_effect = RuntimeError("connection reset")
    backend = RedisCacheBackend(redis_url="redis://x", client=fake_client)

    assert backend.get_json("k") is None  # logged-and-swallowed


def test_redis_backend_set_swallows_client_failure() -> None:
    fake_client = MagicMock()
    fake_client.set.side_effect = RuntimeError("connection reset")
    backend = RedisCacheBackend(redis_url="redis://x", client=fake_client)

    backend.set_json("k", {"v": 1})  # must not raise


def test_redis_backend_delete_swallows_client_failure() -> None:
    fake_client = MagicMock()
    fake_client.delete.side_effect = RuntimeError("connection reset")
    backend = RedisCacheBackend(redis_url="redis://x", client=fake_client)

    backend.delete("k")  # must not raise


def test_redis_backend_get_handles_corrupt_json() -> None:
    fake_client = MagicMock()
    fake_client.get.return_value = "{not valid json"
    backend = RedisCacheBackend(redis_url="redis://x", client=fake_client)

    assert backend.get_json("k") is None


def test_redis_backend_returns_none_when_client_init_failed(monkeypatch) -> None:
    """Simulate redis package missing: backend stays alive with client=None."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("no redis module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    backend = RedisCacheBackend(redis_url="redis://x")

    assert backend.get_json("k") is None
    backend.set_json("k", "v")  # must not raise
    backend.delete("k")  # must not raise


# ---------------------------------------------------------------------------
# 10. Cache hit recorded in usage events (when usage service is wired)
# ---------------------------------------------------------------------------


def test_cache_hit_records_usage_event_when_usage_service_provided() -> None:
    from alphalens.services.usage_service import UsageService

    usage = UsageService()
    cache = CacheService(
        backend=InMemoryCacheBackend(),
        default_ttl_seconds=300,
        usage_service=usage,
    )

    cache.set_cached(build_cache_key("market_data", {"ticker": "NVDA"}), {"x": 1})
    cache.get_cached(build_cache_key("market_data", {"ticker": "NVDA"}))  # hit

    events = usage.list_usage_events()
    cache_hits = [e for e in events if e.event_type == "cache_hit"]
    assert len(cache_hits) == 1
    assert cache_hits[0].metadata.get("namespace") == "market_data"
