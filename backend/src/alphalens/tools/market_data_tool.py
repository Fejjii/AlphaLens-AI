"""Market-data tool.

Thin wrapper around `MarketDataService`: the service decides which
provider to call (Alpha Vantage or the deterministic fallback) and
guarantees a response, so the tool stays simple and provider-agnostic.

Tool contract:
    input:  tickers: list[str]
    output: ToolResult.data = {
        "provider": "alpha_vantage" | "fallback" | "mixed",
        "quotes": [
            {
                "ticker": "...",
                "price": float,
                "previous_close": float,
                "change": float,
                "change_percent": float,
                "currency": "USD",
                "as_of": "<iso8601>",
                "provider": "...",
            },
            ...
        ],
    }
"""

from __future__ import annotations

from alphalens.schemas.market_data import MarketQuote
from alphalens.services.market_data_service import MarketDataService
from alphalens.tools.registry import Tool, ToolResult


def make_market_data_tool(service: MarketDataService) -> Tool:
    def _run(tickers: list[str]) -> ToolResult:
        if not tickers:
            return ToolResult(
                name="market_quote",
                summary="No tickers requested.",
                data={"provider": "fallback", "quotes": []},
            )
        quotes = service.get_quotes(tickers)
        return _quotes_to_result(quotes)

    return Tool(
        name="market_quote",
        description="Return normalized quotes for a list of tickers.",
        func=_run,
        parameters={"tickers": "List of ticker symbols"},
    )


def _quotes_to_result(quotes: list[MarketQuote]) -> ToolResult:
    movers = sorted(quotes, key=lambda q: abs(q.change_percent), reverse=True)[:3]
    summary = "Top movers: " + ", ".join(
        f"{q.ticker} {q.change_percent:+.2%}" for q in movers
    )
    providers = {q.provider for q in quotes}
    aggregate_provider = providers.pop() if len(providers) == 1 else "mixed"
    return ToolResult(
        name="market_quote",
        summary=summary,
        data={
            "provider": aggregate_provider,
            "quotes": [_quote_to_dict(q) for q in quotes],
        },
    )


def _quote_to_dict(quote: MarketQuote) -> dict:
    return {
        "ticker": quote.ticker,
        "price": float(quote.price),
        "previous_close": float(quote.previous_close),
        "change": float(quote.change),
        "change_percent": quote.change_percent,
        "currency": quote.currency,
        "as_of": quote.as_of.isoformat(),
        "provider": quote.provider,
    }
