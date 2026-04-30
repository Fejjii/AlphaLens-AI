"""Tests for token/cost/usage tracking."""

from __future__ import annotations

from pathlib import Path

import pytest

from alphalens.core.config import Settings
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.schemas.usage import UsageEvent, UsageSummary
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.llm_service import LLMService, get_llm_service
from alphalens.services.market_data_service import get_market_data_service
from alphalens.services.rag_service import RAGService
from alphalens.services.usage_service import UsageService
from alphalens.tools.market_data_tool import make_market_data_tool
from alphalens.tools.portfolio_tool import make_portfolio_tool
from alphalens.tools.rag_tool import make_rag_tool
from alphalens.tools.registry import ToolRegistry
from alphalens.tools.risk_tool import make_risk_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOLDINGS_HEADER = (
    "symbol,name,sector,strategy_bucket,quantity,avg_cost,current_price,current_weight\n"
)


def _write_holdings(path: Path) -> Path:
    csv = path / "holdings.csv"
    csv.write_text(
        HOLDINGS_HEADER + "AAA,Alpha,Software,Quality Compounders,100,50,50,0\n",
        encoding="utf-8",
    )
    return csv


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "policy.md").write_text("# Policy\n", encoding="utf-8")
    return kb


def _build_service(
    tmp_path: Path, kb_dir: Path, usage_service: UsageService
) -> ChatService:
    csv = _write_holdings(tmp_path)
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"usage_test_{tmp_path.name}",
    )
    rag_service = RAGService(settings)
    registry = ToolRegistry(usage_service=usage_service)
    registry.register(make_portfolio_tool(holdings_path=csv))
    registry.register(make_risk_tool(holdings_path=csv))
    registry.register(make_market_data_tool(get_market_data_service(settings)))
    registry.register(make_rag_tool(rag_service))
    llm_service = get_llm_service(settings, usage_service=usage_service)
    return ChatService(
        settings=settings,
        rag_service=rag_service,
        approvals_service=ApprovalsService(),
        registry=registry,
        llm_service=llm_service,
    )


# ---------------------------------------------------------------------------
# 1. Fallback LLM usage is recorded
# ---------------------------------------------------------------------------


def test_fallback_llm_usage_is_recorded() -> None:
    usage = UsageService()
    settings = Settings(llm_enabled=False)
    llm_service = get_llm_service(settings, usage_service=usage)

    llm_service.classify_intent(message="Show me my portfolio.")
    llm_service.synthesize_decision(
        intent="portfolio_review",
        recommendation="inform",
        evidence=[],
        deterministic_reasoning=["test"],
    )

    events = usage.list_usage_events()
    assert len(events) == 2
    for ev in events:
        assert ev.event_type == "llm_fallback"
        assert ev.provider == "fallback"
        assert ev.estimated_cost_usd == 0.0


def test_fallback_llm_records_operation_in_metadata() -> None:
    usage = UsageService()
    llm_service = get_llm_service(Settings(llm_enabled=False), usage_service=usage)

    llm_service.classify_intent(message="What is my risk?")

    events = usage.list_usage_events()
    assert events[0].metadata.get("operation") == "classify_intent"


# ---------------------------------------------------------------------------
# 2. Tool usage is recorded
# ---------------------------------------------------------------------------


def test_tool_usage_is_recorded(tmp_path: Path, kb_dir: Path) -> None:
    usage = UsageService()
    csv = _write_holdings(tmp_path)
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"tool_test_{tmp_path.name}",
    )
    registry = ToolRegistry(usage_service=usage)
    registry.register(make_portfolio_tool(holdings_path=csv))

    registry.call("portfolio_analyze")

    events = usage.list_usage_events()
    assert len(events) == 1
    ev = events[0]
    assert ev.tool_name == "portfolio_analyze"
    assert ev.event_type == "tool_call"


def test_tool_usage_captures_provider(tmp_path: Path, kb_dir: Path) -> None:
    usage = UsageService()
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"tool_prov_{tmp_path.name}",
    )
    registry = ToolRegistry(usage_service=usage)
    registry.register(make_market_data_tool(get_market_data_service(settings)))

    registry.call("market_quote", tickers=["NVDA"])

    events = usage.list_usage_events()
    assert len(events) == 1
    assert events[0].provider == "fallback"
    assert events[0].tool_name == "market_quote"


# ---------------------------------------------------------------------------
# 3. Usage summary aggregates events correctly
# ---------------------------------------------------------------------------


def test_usage_summary_aggregates_events() -> None:
    usage = UsageService()

    usage.record_llm_usage(
        event_type="llm_fallback",
        provider="fallback",
        input_tokens=0,
        output_tokens=0,
    )
    usage.record_llm_usage(
        event_type="llm_fallback",
        provider="fallback",
        input_tokens=0,
        output_tokens=0,
    )
    usage.record_tool_usage(tool_name="market_quote", success=True, provider="fallback")
    usage.record_tool_usage(tool_name="rag_retrieve", success=True, provider=None)

    summary = usage.get_usage_summary()

    assert summary.total_events == 4
    assert summary.llm_calls == 2
    assert summary.tool_calls == 2
    assert summary.estimated_cost_usd == 0.0


def test_usage_summary_empty_store() -> None:
    usage = UsageService()
    summary = usage.get_usage_summary()

    assert summary.total_events == 0
    assert summary.total_tokens == 0
    assert summary.estimated_cost_usd == 0.0
    assert summary.llm_calls == 0
    assert summary.tool_calls == 0


def test_cost_estimate_for_gpt4o_mini() -> None:
    usage = UsageService()
    usage.record_llm_usage(
        event_type="llm_call",
        provider="openai",
        model="gpt-4o-mini",
        input_tokens=1000,
        output_tokens=500,
    )

    events = usage.list_usage_events()
    cost = events[0].estimated_cost_usd
    # input: 1000 * 0.00015 / 1000 = 0.00015
    # output: 500 * 0.0006 / 1000 = 0.0003
    assert cost == pytest.approx(0.00015 + 0.0003, rel=1e-4)


# ---------------------------------------------------------------------------
# 4. Agent flow records both LLM and tool events
# ---------------------------------------------------------------------------


def test_agent_flow_records_usage(tmp_path: Path, kb_dir: Path) -> None:
    usage = UsageService()
    service = _build_service(tmp_path, kb_dir, usage)

    service.chat(
        ChatRequest(
            messages=[ChatMessage(role=ChatRole.USER, content="Show me my portfolio.")]
        )
    )

    events = usage.list_usage_events()
    event_types = {ev.event_type for ev in events}
    tool_names = {ev.tool_name for ev in events if ev.tool_name}

    # Both LLM (fallback) and tool events must be present.
    assert "llm_fallback" in event_types
    assert "tool_call" in event_types
    assert "portfolio_analyze" in tool_names

    summary = usage.get_usage_summary()
    assert summary.total_events == len(events)
    assert summary.llm_calls >= 1
    assert summary.tool_calls >= 1


# ---------------------------------------------------------------------------
# 5. /usage/summary and /usage/events API endpoints
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_usage_summary_endpoint(client) -> None:
    response = await client.get("/usage/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_events" in data
    assert "estimated_cost_usd" in data
    assert "llm_calls" in data
    assert "tool_calls" in data


@pytest.mark.anyio
async def test_usage_events_endpoint(client) -> None:
    response = await client.get("/usage/events")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.anyio
async def test_usage_records_after_chat(client) -> None:
    # Trigger a chat so events are recorded.
    await client.post(
        "/agent/chat",
        json={"messages": [{"role": "user", "content": "Show me my portfolio."}]},
    )

    summary_resp = await client.get("/usage/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_events"] > 0
    assert summary["llm_calls"] >= 1
    assert summary["tool_calls"] >= 1

    events_resp = await client.get("/usage/events")
    assert events_resp.status_code == 200
    events = events_resp.json()
    assert len(events) == summary["total_events"]
