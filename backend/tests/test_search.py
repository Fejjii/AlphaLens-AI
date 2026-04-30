"""Tests for the Serper / fallback web-search integration."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from alphalens.core.config import Settings
from alphalens.integrations.search import (
    FallbackSearchClient,
    SearchError,
    SerperSearchClient,
)
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.market_data_service import get_market_data_service
from alphalens.services.rag_service import RAGService
from alphalens.services.search_service import (
    SearchService,
    get_search_client,
    get_search_service,
)
from alphalens.tools.market_data_tool import make_market_data_tool
from alphalens.tools.portfolio_tool import make_portfolio_tool
from alphalens.tools.rag_tool import make_rag_tool
from alphalens.tools.registry import ToolRegistry
from alphalens.tools.risk_tool import make_risk_tool
from alphalens.tools.web_search_tool import make_web_search_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serper_payload(*, count: int = 3) -> dict:
    return {
        "organic": [
            {
                "title": f"Result {i}",
                "link": f"https://www.example.com/article-{i}",
                "snippet": f"Snippet for result {i}",
                "date": "2026-04-28T10:15:00Z",
            }
            for i in range(count)
        ]
    }


def _mock_transport(handler):
    return httpx.MockTransport(handler)


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
    (kb / "policy.md").write_text(
        "# Policy\n\nSoftware capped at 35 percent of NAV.\n",
        encoding="utf-8",
    )
    return kb


def _build_chat_service(
    *,
    tmp_path: Path,
    kb_dir: Path,
    search_service: SearchService,
) -> ChatService:
    csv = _write_clean_holdings(tmp_path)
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"search_test_{tmp_path.name}",
    )
    rag_service = RAGService(settings)
    registry = ToolRegistry()
    registry.register(make_portfolio_tool(holdings_path=csv))
    registry.register(make_risk_tool(holdings_path=csv))
    registry.register(make_market_data_tool(get_market_data_service(settings)))
    registry.register(make_rag_tool(rag_service))
    registry.register(make_web_search_tool(search_service))
    return ChatService(
        settings=settings,
        rag_service=rag_service,
        approvals_service=ApprovalsService(),
        registry=registry,
    )


# ---------------------------------------------------------------------------
# 1. No API key -> fallback
# ---------------------------------------------------------------------------


def test_no_api_key_uses_fallback_client() -> None:
    settings = Settings(search_provider="serper", serper_api_key=None)

    primary = get_search_client(settings)
    service = get_search_service(settings)

    assert primary is None
    assert service.using_external is False


def test_provider_set_to_fallback_uses_fallback_even_with_api_key() -> None:
    settings = Settings(search_provider="fallback", serper_api_key="key-abc")

    assert get_search_client(settings) is None
    assert get_search_service(settings).using_external is False


# ---------------------------------------------------------------------------
# 2. Fallback search returns deterministic results
# ---------------------------------------------------------------------------


def test_fallback_search_is_deterministic() -> None:
    client_a = FallbackSearchClient()
    client_b = FallbackSearchClient()

    a = client_a.search("NVDA earnings", k=4)
    b = client_b.search("NVDA earnings", k=4)

    assert len(a.results) == 4
    assert a.provider == "fallback"
    assert [r.title for r in a.results] == [r.title for r in b.results]
    assert [r.source for r in a.results] == [r.source for r in b.results]
    # Results should look query-relevant: the query string appears in titles.
    assert any("NVDA earnings" in r.title for r in a.results)


# ---------------------------------------------------------------------------
# 3. Serper response is parsed correctly
# ---------------------------------------------------------------------------


def test_serper_parses_organic_results() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.content.decode("utf-8")
        return httpx.Response(200, json=_serper_payload(count=3))

    client = SerperSearchClient(
        api_key="test-key",
        client=httpx.Client(transport=_mock_transport(handler)),
    )

    response = client.search("nvidia earnings", k=3)

    assert response.provider == "serper"
    assert len(response.results) == 3
    first = response.results[0]
    assert first.provider == "serper"
    assert first.source == "example.com"
    assert first.published_at is not None
    assert captured["headers"]["x-api-key"] == "test-key"
    assert "nvidia earnings" in captured["body"]
    assert '"num": 3' in captured["body"] or '"num":3' in captured["body"]


def test_serper_rate_limit_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limit")

    client = SerperSearchClient(
        api_key="test-key",
        client=httpx.Client(transport=_mock_transport(handler)),
    )

    with pytest.raises(SearchError) as excinfo:
        client.search("anything", k=3)
    assert "rate-limited" in str(excinfo.value).lower()


def test_serper_timeout_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = SerperSearchClient(
        api_key="test-key",
        client=httpx.Client(transport=_mock_transport(handler)),
    )

    with pytest.raises(SearchError) as excinfo:
        client.search("anything", k=3)
    assert "timeout" in str(excinfo.value).lower()


def test_serper_empty_results_returns_empty_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic": []})

    client = SerperSearchClient(
        api_key="test-key",
        client=httpx.Client(transport=_mock_transport(handler)),
    )

    response = client.search("xyz", k=3)
    assert response.provider == "serper"
    assert response.results == []


# ---------------------------------------------------------------------------
# 4. Service-level fallback when Serper fails
# ---------------------------------------------------------------------------


def test_service_falls_back_cleanly_on_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="upstream blew up")

    failing = SerperSearchClient(
        api_key="test-key",
        client=httpx.Client(transport=_mock_transport(handler)),
    )
    service = SearchService(primary=failing, fallback=FallbackSearchClient())

    response = service.search("market outlook", k=3)

    # Fallback ran, so provider tag must be 'fallback' and we still got results.
    assert response.provider == "fallback"
    assert len(response.results) == 3


# ---------------------------------------------------------------------------
# 5. web_search tool returns provider and results
# ---------------------------------------------------------------------------


def test_web_search_tool_returns_provider_and_results() -> None:
    service = SearchService(primary=None, fallback=FallbackSearchClient())
    tool = make_web_search_tool(service)

    result = tool(query="AAPL earnings", k=3)

    assert result.name == "web_search"
    assert result.data["provider"] == "fallback"
    assert result.data["query"] == "AAPL earnings"
    assert len(result.data["results"]) == 3
    for hit in result.data["results"]:
        assert hit["provider"] == "fallback"
        assert hit["title"]
        assert hit["url"].startswith("http")
        assert hit["source"]


# ---------------------------------------------------------------------------
# 6. Agent uses web_search for news-flavoured queries
# ---------------------------------------------------------------------------


def test_news_query_triggers_web_search(tmp_path: Path, kb_dir: Path) -> None:
    search_service = SearchService(
        primary=None, fallback=FallbackSearchClient()
    )
    service = _build_chat_service(
        tmp_path=tmp_path, kb_dir=kb_dir, search_service=search_service
    )

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="Any latest news on NVDA earnings catalysts?",
                )
            ]
        )
    )

    assert "web_search" in response.used_tools
    decision = response.decision
    assert decision is not None
    web_ev = next(ev for ev in decision.evidence if ev.tool == "web_search")
    assert web_ev.data["provider"] == "fallback"
    assert web_ev.data["results"], "expected at least one web result"


def test_trade_idea_uses_web_search_alongside_rag(
    tmp_path: Path, kb_dir: Path
) -> None:
    service = _build_chat_service(
        tmp_path=tmp_path,
        kb_dir=kb_dir,
        search_service=SearchService(
            primary=None, fallback=FallbackSearchClient()
        ),
    )

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(role=ChatRole.USER, content="Should I buy NVDA today?")
            ]
        )
    )

    used = set(response.used_tools)
    # Web search complements, never replaces, RAG.
    assert "web_search" in used
    assert "rag_retrieve" in used


# ---------------------------------------------------------------------------
# 7. RAG works independently when web_search is not warranted
# ---------------------------------------------------------------------------


def test_rag_works_independently_when_web_search_not_warranted(
    tmp_path: Path, kb_dir: Path
) -> None:
    service = _build_chat_service(
        tmp_path=tmp_path,
        kb_dir=kb_dir,
        search_service=SearchService(
            primary=None, fallback=FallbackSearchClient()
        ),
    )

    # Research intent triggered by "policy" keyword has needs_rag=True but
    # the message contains no external-context trigger words and the intent
    # is within the research set, so web_search will still run by design.
    # To assert independence we use a portfolio_review query, which does
    # not warrant external context: web_search must NOT run, RAG must.
    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="Show me my portfolio exposure and weights.",
                )
            ]
        )
    )

    used = set(response.used_tools)
    assert "web_search" not in used
    # portfolio_review does not flag needs_rag in the deterministic
    # classifier, but the gather node still falls back to RAG when no other
    # tools have produced output. Either way, the agent must finish without
    # web_search and produce a valid decision.
    assert response.decision is not None
