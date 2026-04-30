"""Market-data service: provider selection, caching, and graceful fallback.

Selection rule:

    if MARKET_DATA_PROVIDER == "alpha_vantage" and ALPHA_VANTAGE_API_KEY
        -> AlphaVantageMarketDataClient
    else
        -> DeterministicFallbackMarketDataClient

When the primary client raises `MarketDataError` we log the failure and
fall through to the deterministic client so the agent never crashes on
provider issues. Per-ticker failures degrade gracefully: a successful
quote for AAPL is returned even if MSFT fails.

Caching is optional and applied at the per-ticker boundary so that batch
queries also benefit from any cached individual quotes. Cache failures are
swallowed by ``CacheService`` and never break the call path.
"""

from __future__ import annotations

from alphalens.core.config import Settings
from alphalens.core.logging import get_logger
from alphalens.integrations.market_data import (
    AlphaVantageMarketDataClient,
    DeterministicFallbackMarketDataClient,
    MarketDataClient,
    MarketDataError,
)
from alphalens.schemas.market_data import MarketQuote
from alphalens.services.cache_service import CacheService, build_cache_key

logger = get_logger(__name__)

_NAMESPACE = "market_data"


class MarketDataService:
    """Wraps a primary client and a deterministic fallback."""

    def __init__(
        self,
        *,
        primary: MarketDataClient | None,
        fallback: MarketDataClient,
        cache: CacheService | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._cache = cache

    @property
    def using_external(self) -> bool:
        """True when an external provider is configured."""
        return self._primary is not None

    def get_quote(self, ticker: str) -> MarketQuote:
        cached = self._get_cached(ticker)
        if cached is not None:
            return cached
        quote = self._fetch_quote(ticker)
        self._set_cached(ticker, quote)
        return quote

    def get_quotes(self, tickers: list[str]) -> list[MarketQuote]:
        return [self.get_quote(t) for t in tickers]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_quote(self, ticker: str) -> MarketQuote:
        if self._primary is None:
            return self._fallback.get_quote(ticker)
        try:
            return self._primary.get_quote(ticker)
        except MarketDataError as exc:
            logger.warning(
                "market_data_fallback",
                ticker=ticker,
                error=str(exc),
                reason="primary_error",
            )
            return self._fallback.get_quote(ticker)

    def _get_cached(self, ticker: str) -> MarketQuote | None:
        if self._cache is None:
            return None
        key = build_cache_key(_NAMESPACE, {"op": "quote", "ticker": ticker.upper()})
        raw = self._cache.get_cached(key)
        if raw is None:
            return None
        try:
            return MarketQuote.model_validate(raw)
        except Exception as exc:
            logger.warning("cache_decode_failed", namespace=_NAMESPACE, error=str(exc))
            self._cache.delete(key)
            return None

    def _set_cached(self, ticker: str, quote: MarketQuote) -> None:
        if self._cache is None:
            return
        key = build_cache_key(_NAMESPACE, {"op": "quote", "ticker": ticker.upper()})
        self._cache.set_cached(key, quote.model_dump(mode="json"))


def get_market_data_client(settings: Settings) -> MarketDataClient | None:
    """Build the primary client, or None when external provider is disabled."""

    if (
        settings.market_data_provider == "alpha_vantage"
        and settings.alpha_vantage_api_key
    ):
        try:
            return AlphaVantageMarketDataClient(
                api_key=settings.alpha_vantage_api_key,
                timeout_seconds=settings.market_data_timeout_seconds,
            )
        except MarketDataError as exc:
            logger.warning("market_data_client_init_failed", error=str(exc))
            return None
    return None


def get_market_data_service(
    settings: Settings,
    *,
    cache: CacheService | None = None,
) -> MarketDataService:
    return MarketDataService(
        primary=get_market_data_client(settings),
        fallback=DeterministicFallbackMarketDataClient(),
        cache=cache,
    )
