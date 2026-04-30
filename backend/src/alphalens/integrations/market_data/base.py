"""Protocol for market-data clients."""

from __future__ import annotations

from typing import Protocol

from alphalens.schemas.market_data import MarketQuote


class MarketDataError(Exception):
    """Raised by a `MarketDataClient` for any provider-side failure.

    Includes: missing API key, malformed payload, rate-limit / "Note"
    response, unknown ticker, network timeout, or unexpected status.
    The service layer catches this to fall back deterministically.
    """


class MarketDataClient(Protocol):
    """Two-method contract used by the market-data service."""

    def get_quote(self, ticker: str) -> MarketQuote:
        """Return a single normalized quote.

        Raises `MarketDataError` on any provider-side failure.
        """
        ...

    def get_quotes(self, tickers: list[str]) -> list[MarketQuote]:
        """Return quotes for a list of tickers.

        Implementations may issue per-ticker requests or batch them.
        Raises `MarketDataError` on any provider-side failure.
        """
        ...
