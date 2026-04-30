"""Tests for the Alpha Vantage / fallback market-data integration."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from alphalens.core.config import Settings
from alphalens.integrations.market_data import (
    AlphaVantageMarketDataClient,
    DeterministicFallbackMarketDataClient,
    MarketDataError,
)
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.market_data_service import (
    MarketDataService,
    get_market_data_client,
    get_market_data_service,
)
from alphalens.services.rag_service import RAGService
from alphalens.tools.market_data_tool import make_market_data_tool
from alphalens.tools.portfolio_tool import make_portfolio_tool
from alphalens.tools.rag_tool import make_rag_tool
from alphalens.tools.registry import ToolRegistry
from alphalens.tools.risk_tool import make_risk_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _alpha_vantage_payload(
    *,
    symbol: str = "NVDA",
    price: str = "750.1234",
    previous_close: str = "740.0000",
    change: str = "10.1234",
    change_percent: str = "1.3680%",
    latest_day: str = "2026-04-28",
) -> dict:
    return {
        "Global Quote": {
            "01. symbol": symbol,
            "02. open": "745.0000",
            "03. high": "755.0000",
            "04. low": "740.0000",
            "05. price": price,
            "06. volume": "10000000",
            "07. latest trading day": latest_day,
            "08. previous close": previous_close,
            "09. change": change,
            "10. change percent": change_percent,
        }
    }


def _make_mock_transport(handler):
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# 1. No API key -> fallback client is selected
# ---------------------------------------------------------------------------


def test_no_api_key_uses_fallback_client() -> None:
    settings = Settings(market_data_provider="alpha_vantage", alpha_vantage_api_key=None)

    primary = get_market_data_client(settings)
    service = get_market_data_service(settings)

    assert primary is None
    assert service.using_external is False


def test_provider_set_to_fallback_uses_fallback_even_with_api_key() -> None:
    settings = Settings(
        market_data_provider="fallback", alpha_vantage_api_key="key-123"
    )

    assert get_market_data_client(settings) is None
    assert get_market_data_service(settings).using_external is False


# ---------------------------------------------------------------------------
# 2. Fallback quote is deterministic across calls and instances
# ---------------------------------------------------------------------------


def test_fallback_quote_is_deterministic() -> None:
    client_a = DeterministicFallbackMarketDataClient()
    client_b = DeterministicFallbackMarketDataClient()

    quote_a = client_a.get_quote("NVDA")
    quote_b = client_b.get_quote("NVDA")

    assert quote_a.ticker == "NVDA"
    assert quote_a.provider == "fallback"
    assert quote_a.price == quote_b.price
    assert quote_a.previous_close == quote_b.previous_close
    assert quote_a.change_percent == quote_b.change_percent


# ---------------------------------------------------------------------------
# 3. Alpha Vantage response is parsed correctly with mocked httpx
# ---------------------------------------------------------------------------


def test_alpha_vantage_parses_global_quote_payload() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json=_alpha_vantage_payload(symbol="NVDA"))

    transport = _make_mock_transport(handler)
    http_client = httpx.Client(transport=transport)
    client = AlphaVantageMarketDataClient(
        api_key="test-key", client=http_client
    )

    quote = client.get_quote("NVDA")

    assert quote.ticker == "NVDA"
    assert quote.provider == "alpha_vantage"
    assert float(quote.price) == pytest.approx(750.1234)
    assert float(quote.previous_close) == pytest.approx(740.0)
    assert float(quote.change) == pytest.approx(10.1234)
    assert quote.change_percent == pytest.approx(0.013680, rel=1e-4)
    assert "function=GLOBAL_QUOTE" in captured["url"]
    assert "symbol=NVDA" in captured["url"]
    assert "apikey=test-key" in captured["url"]


def test_alpha_vantage_rate_limit_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "Note": (
                    "Thank you for using Alpha Vantage! Our standard API rate "
                    "limit is 25 requests per day."
                )
            },
        )

    client = AlphaVantageMarketDataClient(
        api_key="test-key",
        client=httpx.Client(transport=_make_mock_transport(handler)),
    )

    with pytest.raises(MarketDataError) as excinfo:
        client.get_quote("NVDA")
    assert "rate-limited" in str(excinfo.value).lower()


def test_alpha_vantage_invalid_ticker_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"Error Message": "Invalid API call. Please retry."},
        )

    client = AlphaVantageMarketDataClient(
        api_key="test-key",
        client=httpx.Client(transport=_make_mock_transport(handler)),
    )

    with pytest.raises(MarketDataError):
        client.get_quote("ZZZZ")


def test_alpha_vantage_timeout_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = AlphaVantageMarketDataClient(
        api_key="test-key",
        client=httpx.Client(transport=_make_mock_transport(handler)),
    )

    with pytest.raises(MarketDataError) as excinfo:
        client.get_quote("NVDA")
    assert "timeout" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# 4. Service-level fallback when Alpha Vantage fails
# ---------------------------------------------------------------------------


def test_service_falls_back_cleanly_on_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream blew up")

    failing = AlphaVantageMarketDataClient(
        api_key="test-key",
        client=httpx.Client(transport=_make_mock_transport(handler)),
    )
    service = MarketDataService(
        primary=failing, fallback=DeterministicFallbackMarketDataClient()
    )

    quote = service.get_quote("NVDA")

    assert quote.ticker == "NVDA"
    # Fallback is the deterministic client, so the quote must be tagged with it.
    assert quote.provider == "fallback"


# ---------------------------------------------------------------------------
# 5. market_quote tool returns a `provider` field
# ---------------------------------------------------------------------------


def test_market_quote_tool_returns_provider_field() -> None:
    service = MarketDataService(
        primary=None, fallback=DeterministicFallbackMarketDataClient()
    )
    tool = make_market_data_tool(service)

    result = tool(tickers=["NVDA", "MSFT"])

    assert result.name == "market_quote"
    assert result.data["provider"] == "fallback"
    assert len(result.data["quotes"]) == 2
    for quote in result.data["quotes"]:
        assert quote["provider"] == "fallback"
        assert "price" in quote
        assert "previous_close" in quote
        assert "change_percent" in quote


# ---------------------------------------------------------------------------
# 6. Agent trade-idea flow still uses market_quote with provider field
# ---------------------------------------------------------------------------


HOLDINGS_HEADER = (
    "symbol,name,sector,strategy_bucket,quantity,avg_cost,current_price,current_weight\n"
)


def _write_clean_holdings(path: Path) -> Path:
    csv = path / "holdings.csv"
    csv.write_text(
        HOLDINGS_HEADER
        + "AAA,Alpha,Software,Quality Compounders,100,50,50,0\n"
        + "AAB,Alpha B,Software,Quality Compounders,100,50,50,0\n"
        + "AAC,Alpha C,Software,Quality Compounders,100,50,50,0\n"
        + "ENE,Energy Co,Energy,Defensive,100,50,50,0\n"
        + "FIN,Finance Co,Financials,Defensive,100,50,50,0\n"
        + "IND,Industrial Co,Industrials,Defensive,100,50,50,0\n"
        + "HLT,Health Co,Healthcare,Defensive,100,50,50,0\n"
        + "UTL,Utility Co,Utilities,Defensive,100,50,50,0\n"
        + "CST,Staples Co,Consumer Staples,Defensive,100,50,50,0\n"
        + "MAT,Materials Co,Materials,Defensive,100,50,50,0\n"
        + "REA,Real Estate Co,Real Estate,Defensive,100,50,50,0\n",
        encoding="utf-8",
    )
    return csv


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "policy.md").write_text("# Policy\n", encoding="utf-8")
    return kb


def test_trade_idea_flow_uses_market_quote_with_provider_field(
    tmp_path: Path, kb_dir: Path
) -> None:
    csv = _write_clean_holdings(tmp_path)
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"market_test_{tmp_path.name}",
    )
    rag_service = RAGService(settings)
    md_service = MarketDataService(
        primary=None, fallback=DeterministicFallbackMarketDataClient()
    )
    registry = ToolRegistry()
    registry.register(make_portfolio_tool(holdings_path=csv))
    registry.register(make_risk_tool(holdings_path=csv))
    registry.register(make_market_data_tool(md_service))
    registry.register(make_rag_tool(rag_service))
    service = ChatService(
        settings=settings,
        rag_service=rag_service,
        approvals_service=ApprovalsService(),
        registry=registry,
    )

    response = service.chat(
        ChatRequest(
            messages=[ChatMessage(role=ChatRole.USER, content="Should I buy NVDA?")]
        )
    )

    assert "market_quote" in response.used_tools
    decision = response.decision
    assert decision is not None
    quote_ev = next(ev for ev in decision.evidence if ev.tool == "market_quote")
    assert quote_ev.data["provider"] == "fallback"
    assert any(q["ticker"] == "NVDA" for q in quote_ev.data["quotes"])
    assert all(q["provider"] == "fallback" for q in quote_ev.data["quotes"])
