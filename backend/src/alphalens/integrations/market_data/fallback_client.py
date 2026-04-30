"""Deterministic offline market-data client.

Used for local development, tests, and as a safety net when the configured
external provider fails. Prices and changes are derived from a hash of the
ticker so values are stable across runs.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from alphalens.integrations.market_data.base import MarketDataClient
from alphalens.schemas.market_data import MarketQuote

PROVIDER_NAME = "fallback"


def _seed(ticker: str) -> int:
    digest = hashlib.blake2b(ticker.upper().encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _price(ticker: str) -> Decimal:
    """Deterministic price in [10.00, 1010.00]."""

    base = _seed(ticker) % 100_000 / 100.0
    return Decimal(f"{10.0 + base:.2f}")


def _change_pct(ticker: str) -> float:
    """Deterministic day-change percentage in [-0.05, +0.05]."""

    raw = (_seed(ticker) >> 16) % 10_001
    pct = (raw / 10_000.0) * 0.10 - 0.05
    return round(pct, 4)


class DeterministicFallbackMarketDataClient(MarketDataClient):
    """Hash-derived fake quotes that never raise."""

    def get_quote(self, ticker: str) -> MarketQuote:
        symbol = ticker.upper()
        price = _price(symbol)
        change_pct = _change_pct(symbol)
        # previous_close = price / (1 + pct), then change = price - previous_close.
        prev = (price / (Decimal(1) + Decimal(str(change_pct)))).quantize(Decimal("0.01"))
        change = (price - prev).quantize(Decimal("0.01"))
        return MarketQuote(
            ticker=symbol,
            price=price,
            previous_close=prev,
            change=change,
            change_percent=change_pct,
            currency="USD",
            as_of=datetime.now(tz=UTC),
            provider=PROVIDER_NAME,
        )

    def get_quotes(self, tickers: list[str]) -> list[MarketQuote]:
        return [self.get_quote(t) for t in tickers]
