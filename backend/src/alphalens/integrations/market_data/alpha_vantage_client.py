"""Alpha Vantage market-data client (GLOBAL_QUOTE endpoint).

Translates the provider's nested string payload into our normalized
`MarketQuote` schema and surfaces every failure mode as `MarketDataError`
so the service layer can fall back deterministically.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from alphalens.core.logging import get_logger
from alphalens.integrations.market_data.base import MarketDataClient, MarketDataError
from alphalens.schemas.market_data import MarketQuote

logger = get_logger(__name__)

PROVIDER_NAME = "alpha_vantage"
DEFAULT_BASE_URL = "https://www.alphavantage.co/query"


class AlphaVantageMarketDataClient(MarketDataClient):
    """Calls the GLOBAL_QUOTE endpoint per ticker."""

    def __init__(
        self,
        *,
        api_key: str | None,
        timeout_seconds: float = 10.0,
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise MarketDataError("Alpha Vantage API key is not configured.")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._base_url = base_url
        self._client = client  # injected client owns its own lifecycle.

    def get_quote(self, ticker: str) -> MarketQuote:
        symbol = ticker.upper().strip()
        if not symbol:
            raise MarketDataError("Ticker must be non-empty.")
        payload = self._fetch(symbol)
        return _parse_global_quote(payload, symbol=symbol)

    def get_quotes(self, tickers: list[str]) -> list[MarketQuote]:
        # GLOBAL_QUOTE is single-symbol; serial calls keep things simple and
        # respect Alpha Vantage's strict rate limits.
        return [self.get_quote(t) for t in tickers]

    def _fetch(self, symbol: str) -> dict[str, Any]:
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": self._api_key,
        }
        try:
            if self._client is not None:
                response = self._client.get(self._base_url, params=params)
            else:
                with httpx.Client(timeout=self._timeout) as client:
                    response = client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            raise MarketDataError(f"Alpha Vantage timeout for {symbol}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise MarketDataError(
                f"Alpha Vantage transport error for {symbol}: {exc}"
            ) from exc

        if response.status_code != 200:
            raise MarketDataError(
                f"Alpha Vantage HTTP {response.status_code} for {symbol}."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise MarketDataError(
                f"Alpha Vantage returned non-JSON for {symbol}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise MarketDataError(
                f"Alpha Vantage returned unexpected payload type for {symbol}."
            )

        # Rate limit and informational responses come back HTTP 200 with a
        # `Note` or `Information` key and no quote data.
        if "Note" in payload or "Information" in payload:
            message = payload.get("Note") or payload.get("Information")
            raise MarketDataError(f"Alpha Vantage rate-limited: {message}")
        if "Error Message" in payload:
            raise MarketDataError(
                f"Alpha Vantage error for {symbol}: {payload['Error Message']}"
            )
        return payload


def _parse_global_quote(payload: dict[str, Any], *, symbol: str) -> MarketQuote:
    quote = payload.get("Global Quote")
    if not isinstance(quote, dict) or not quote:
        raise MarketDataError(f"Alpha Vantage returned empty quote for {symbol}.")

    try:
        price = Decimal(quote["05. price"])
        previous_close = Decimal(quote["08. previous close"])
        change = Decimal(quote["09. change"])
        change_percent_raw = str(quote["10. change percent"]).rstrip("%").strip()
        change_percent = float(change_percent_raw) / 100.0
        latest_day = str(quote.get("07. latest trading day", ""))
    except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
        raise MarketDataError(
            f"Alpha Vantage payload malformed for {symbol}: {exc}"
        ) from exc

    as_of = _parse_latest_day(latest_day)
    return MarketQuote(
        ticker=symbol,
        price=price,
        previous_close=previous_close,
        change=change,
        change_percent=change_percent,
        currency="USD",
        as_of=as_of,
        provider=PROVIDER_NAME,
    )


def _parse_latest_day(value: str) -> datetime:
    if not value:
        return datetime.now(tz=UTC)
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(tz=UTC)
