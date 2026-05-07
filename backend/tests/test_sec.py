"""Tests for the SEC EDGAR / fallback filing integration."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from alphalens.core.config import Settings
from alphalens.integrations.sec.base import SECError
from alphalens.integrations.sec.fallback_client import FallbackSECClient
from alphalens.integrations.sec.sec_edgar_client import SecEdgarClient, _parse_filings
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.schemas.sec import CompanyFiling, FilingSearchResponse, FilingSection
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.market_data_service import get_market_data_service
from alphalens.services.rag_service import RAGService
from alphalens.services.sec_service import SECService, get_sec_service
from alphalens.tools.macro_tool import make_macro_snapshot_tool
from alphalens.tools.market_data_tool import make_market_data_tool
from alphalens.tools.portfolio_tool import make_portfolio_tool
from alphalens.tools.rag_tool import make_rag_tool
from alphalens.tools.registry import ToolRegistry
from alphalens.tools.risk_tool import make_risk_tool
from alphalens.tools.sec_tool import make_sec_filings_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOLDINGS_HEADER = (
    "symbol,name,sector,strategy_bucket,quantity,avg_cost,current_price,current_weight\n"
)


def _write_clean_holdings(path: Path) -> Path:
    csv = path / "holdings.csv"
    csv.write_text(
        HOLDINGS_HEADER
        + "AAA,Alpha,Software,Quality Compounders,100,50,50,0\n"
        + "ENE,Energy Co,Energy,Defensive,100,50,50,0\n",
        encoding="utf-8",
    )
    return csv


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "policy.md").write_text("# Policy\n", encoding="utf-8")
    return kb


def _submissions_payload(
    name: str = "NVIDIA Corp",
    forms: list[str] | None = None,
    dates: list[str] | None = None,
    accessions: list[str] | None = None,
) -> dict:
    if forms is None:
        forms = ["10-K", "10-Q", "8-K"]
    if dates is None:
        dates = ["2024-01-26", "2024-08-28", "2024-02-21"]
    if accessions is None:
        accessions = [
            "0001045810-24-000009",
            "0001045810-24-000040",
            "0001045810-24-000011",
        ]
    return {
        "cik": "1045810",
        "name": name,
        "filings": {
            "recent": {
                "form": forms,
                "filingDate": dates,
                "accessionNumber": accessions,
            }
        },
    }


# ---------------------------------------------------------------------------
# 1. Fallback SEC client returns deterministic sections
# ---------------------------------------------------------------------------


def test_fallback_sec_client_returns_deterministic_sections() -> None:
    client_a = FallbackSECClient()
    client_b = FallbackSECClient()

    sections_a = client_a.get_filing_sections("NVDA", form_type="10-K")
    sections_b = client_b.get_filing_sections("NVDA", form_type="10-K")

    assert len(sections_a) == len(sections_b)
    for s_a, s_b in zip(sections_a, sections_b):
        assert s_a.section == s_b.section
        assert s_a.text == s_b.text
        assert s_a.provider == "fallback"


def test_fallback_sec_sections_cover_required_topics() -> None:
    client = FallbackSECClient()
    sections = client.get_filing_sections("NVDA", form_type="10-K")

    section_names = {s.section for s in sections}
    assert "Risk Factors" in section_names
    assert "Business Overview" in section_names
    assert "Management Discussion" in section_names
    assert "AI / Technology Exposure" in section_names


def test_fallback_sec_unknown_ticker_returns_sections() -> None:
    client = FallbackSECClient()
    sections = client.get_filing_sections("ZZZZ", form_type="10-K")

    assert len(sections) > 0
    for s in sections:
        assert s.ticker == "ZZZZ"
        assert s.provider == "fallback"


def test_fallback_sec_recent_filings_returns_metadata() -> None:
    client = FallbackSECClient()
    resp = client.get_recent_filings("NVDA", form_types=["10-K", "10-Q"], limit=2)

    assert resp.ticker == "NVDA"
    assert resp.provider == "fallback"
    assert len(resp.filings) <= 2
    for f in resp.filings:
        assert isinstance(f, CompanyFiling)
        assert f.ticker == "NVDA"
        assert f.form_type in {"10-K", "10-Q"}
        assert f.filing_url.startswith("https://www.sec.gov")


# ---------------------------------------------------------------------------
# 2. SEC EDGAR metadata response parses with mocked httpx
# ---------------------------------------------------------------------------


def test_sec_edgar_parses_submissions_payload() -> None:
    payload = _submissions_payload()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "submissions" in url:
            return httpx.Response(200, json=payload)
        # company_tickers fallback (not needed for known ticker)
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)

    import unittest.mock as mock

    def mock_get(url, *, headers=None, timeout=None):
        req = httpx.Request("GET", url, headers=headers or {})
        return transport.handle_request(req)

    client = SecEdgarClient(user_agent="Test Agent test@test.com", timeout=10.0)
    with mock.patch("httpx.get", side_effect=mock_get):
        result = client.get_recent_filings("NVDA", form_types=["10-K", "10-Q"], limit=3)

    assert result.ticker == "NVDA"
    assert result.provider == "sec_edgar"
    assert len(result.filings) == 2  # one 10-K and one 10-Q from the payload
    form_types = {f.form_type for f in result.filings}
    assert "10-K" in form_types
    assert "10-Q" in form_types

    ten_k = next(f for f in result.filings if f.form_type == "10-K")
    assert ten_k.filing_date == date(2024, 1, 26)
    assert ten_k.accession_number == "0001045810-24-000009"
    assert ten_k.company_name == "NVIDIA Corp"
    assert "sec.gov" in ten_k.filing_url


def test_sec_edgar_http_error_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    transport = httpx.MockTransport(handler)
    import unittest.mock as mock

    def mock_get(url, *, headers=None, timeout=None):
        req = httpx.Request("GET", url, headers=headers or {})
        return transport.handle_request(req)

    client = SecEdgarClient(user_agent="Test Agent test@test.com")
    with mock.patch("httpx.get", side_effect=mock_get):
        with pytest.raises(SECError) as exc_info:
            client.get_recent_filings("NVDA")
    assert "500" in str(exc_info.value)


def test_sec_edgar_rate_limit_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="too many requests")

    transport = httpx.MockTransport(handler)
    import unittest.mock as mock

    def mock_get(url, *, headers=None, timeout=None):
        req = httpx.Request("GET", url, headers=headers or {})
        return transport.handle_request(req)

    client = SecEdgarClient(user_agent="Test Agent test@test.com")
    with mock.patch("httpx.get", side_effect=mock_get):
        with pytest.raises(SECError) as exc_info:
            client.get_recent_filings("NVDA")
    assert "rate limit" in str(exc_info.value).lower()


def test_sec_edgar_timeout_raises() -> None:
    import unittest.mock as mock

    def mock_get(url, *, headers=None, timeout=None):
        raise httpx.ConnectTimeout("timed out")

    client = SecEdgarClient(user_agent="Test Agent test@test.com")
    with mock.patch("httpx.get", side_effect=mock_get):
        with pytest.raises(SECError) as exc_info:
            client.get_recent_filings("NVDA")
    assert "timed out" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 3. SEC provider error falls back cleanly
# ---------------------------------------------------------------------------


def test_sec_service_falls_back_on_provider_error() -> None:
    failing = MagicMock()
    failing.get_filing_sections.side_effect = SECError("EDGAR down")

    service = SECService.__new__(SECService)
    service._primary = failing
    service._fallback = FallbackSECClient()

    sections = service.get_filing_sections("NVDA", form_type="10-K")

    assert len(sections) > 0
    assert all(s.provider == "fallback" for s in sections)
    failing.get_filing_sections.assert_called_once()


def test_sec_service_filings_falls_back_on_error() -> None:
    failing = MagicMock()
    failing.get_recent_filings.side_effect = SECError("network error")

    service = SECService.__new__(SECService)
    service._primary = failing
    service._fallback = FallbackSECClient()

    resp = service.get_recent_filings("NVDA")

    assert resp.provider == "fallback"
    assert resp.ticker == "NVDA"


def test_fallback_provider_setting_uses_fallback() -> None:
    settings = Settings(sec_provider="fallback")
    service = get_sec_service(settings)
    snapshot = service.get_filing_sections("NVDA")

    assert all(s.provider == "fallback" for s in snapshot)


# ---------------------------------------------------------------------------
# 4. sec_filings tool returns filings and sections
# ---------------------------------------------------------------------------


def test_sec_filings_tool_returns_filings_and_sections() -> None:
    service = SECService(Settings(sec_provider="fallback"))
    tool = make_sec_filings_tool(service)

    result = tool(ticker="NVDA")

    assert result.name == "sec_filings"
    assert result.data["ticker"] == "NVDA"
    assert result.data["provider"] == "fallback"
    assert len(result.data["filings"]) > 0
    assert len(result.data["sections"]) > 0

    for filing in result.data["filings"]:
        assert "form_type" in filing
        assert "filing_date" in filing
        assert "filing_url" in filing

    section_names = {s["section"] for s in result.data["sections"]}
    assert "Risk Factors" in section_names
    assert "Business Overview" in section_names


def test_sec_filings_tool_with_10q() -> None:
    service = SECService(Settings(sec_provider="fallback"))
    tool = make_sec_filings_tool(service)

    result = tool(ticker="MSFT", form_type="10-Q")

    assert result.data["ticker"] == "MSFT"
    for filing in result.data["filings"]:
        assert filing["form_type"] == "10-Q"


# ---------------------------------------------------------------------------
# 5. Agent query for 10-K risk factors uses sec_filings
# ---------------------------------------------------------------------------


def _build_agent_service(
    tmp_path: Path, kb_dir: Path
) -> tuple[ChatService, ApprovalsService]:
    csv = _write_clean_holdings(tmp_path)
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"sec_test_{tmp_path.name}",
        sec_provider="fallback",
        macro_data_provider="fallback",
    )
    rag_service = RAGService(settings)
    approvals_service = ApprovalsService()
    registry = ToolRegistry()
    registry.register(make_portfolio_tool(holdings_path=csv))
    registry.register(make_risk_tool(holdings_path=csv))
    registry.register(make_market_data_tool(get_market_data_service(settings)))
    registry.register(make_rag_tool(rag_service))
    registry.register(make_macro_snapshot_tool(
        __import__("alphalens.services.macro_service", fromlist=["MacroService"]).MacroService(settings)
    ))
    registry.register(make_sec_filings_tool(SECService(settings)))
    service = ChatService(
        settings=settings,
        rag_service=rag_service,
        approvals_service=approvals_service,
        registry=registry,
    )
    return service, approvals_service


def test_agent_sec_query_uses_sec_filings(tmp_path: Path, kb_dir: Path) -> None:
    service, _ = _build_agent_service(tmp_path, kb_dir)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="What risks does NVDA mention in its 10-K?",
                )
            ]
        )
    )

    assert "sec_filings" in response.used_tools
    decision = response.decision
    assert decision is not None
    sec_ev = next(ev for ev in decision.evidence if ev.tool == "sec_filings")
    assert sec_ev.data["ticker"] == "NVDA"
    section_names = {s["section"] for s in sec_ev.data["sections"]}
    assert "Risk Factors" in section_names


# ---------------------------------------------------------------------------
# 6. Trade idea with ticker uses sec_filings when research/risk terms present
# ---------------------------------------------------------------------------


def test_trade_idea_with_ticker_uses_sec_filings(tmp_path: Path, kb_dir: Path) -> None:
    service, _ = _build_agent_service(tmp_path, kb_dir)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="Should I buy NVDA? I want to review its fundamentals and risk factors.",
                )
            ]
        )
    )

    assert "sec_filings" in response.used_tools
    assert "market_quote" in response.used_tools
    decision = response.decision
    assert decision is not None
    # The deterministic classifier may pick trade_idea or risk_check depending
    # on which keyword matches first; both are valid for this query. What matters
    # is that SEC filings and market data were retrieved.
    assert decision.intent in {"trade_idea", "risk_check", "investment_recommendation"}
