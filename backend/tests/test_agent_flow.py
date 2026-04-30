from __future__ import annotations

from pathlib import Path

import pytest

from alphalens.core.config import Settings
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.market_data_service import get_market_data_service
from alphalens.services.rag_service import RAGService
from alphalens.tools.market_data_tool import make_market_data_tool
from alphalens.tools.portfolio_tool import make_portfolio_tool
from alphalens.tools.rag_tool import make_rag_tool
from alphalens.tools.registry import ToolRegistry
from alphalens.tools.risk_tool import make_risk_tool


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


def _write_violating_holdings(path: Path) -> Path:
    # BIG is ~95% of NAV -> single-name violation.
    csv = path / "holdings.csv"
    csv.write_text(
        HOLDINGS_HEADER
        + "BIG,Big,Software,Quality Compounders,100,100,100,0.95\n"
        + "SML,Small,Energy,Defensive,5,100,100,0.05\n",
        encoding="utf-8",
    )
    return csv


def _build_service(
    *, tmp_path: Path, holdings_csv: Path, kb_dir: Path
) -> tuple[ChatService, ApprovalsService]:
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"agent_flow_{tmp_path.name}",
    )
    rag_service = RAGService(settings)
    approvals_service = ApprovalsService()
    registry = ToolRegistry()
    registry.register(make_portfolio_tool(holdings_path=holdings_csv))
    registry.register(make_risk_tool(holdings_path=holdings_csv))
    registry.register(make_market_data_tool(get_market_data_service(settings)))
    registry.register(make_rag_tool(rag_service))
    return (
        ChatService(
            settings=settings,
            rag_service=rag_service,
            approvals_service=approvals_service,
            registry=registry,
        ),
        approvals_service,
    )


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "policy.md").write_text(
        "# Policy\n\n## Sector limits\n\nSoftware capped at 35 percent of NAV.\n",
        encoding="utf-8",
    )
    return kb


def test_portfolio_review_runs_full_pipeline(tmp_path: Path, kb_dir: Path) -> None:
    csv = _write_clean_holdings(tmp_path)
    service, _ = _build_service(tmp_path=tmp_path, holdings_csv=csv, kb_dir=kb_dir)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(role=ChatRole.USER, content="Show me my portfolio exposure.")
            ]
        )
    )

    assert response.message.role is ChatRole.ASSISTANT
    decision = response.decision
    assert decision is not None
    assert decision.intent == "portfolio_review"
    assert "portfolio_analyze" in response.used_tools
    assert "risk_check" in response.used_tools
    tools_in_evidence = {ev.tool for ev in decision.evidence}
    assert {"portfolio_analyze", "risk_check"} <= tools_in_evidence
    assert decision.risk_level.value == "low"
    assert decision.confidence == 0.7


def test_violation_triggers_escalate_and_approval(tmp_path: Path, kb_dir: Path) -> None:
    csv = _write_violating_holdings(tmp_path)
    service, approvals_service = _build_service(
        tmp_path=tmp_path, holdings_csv=csv, kb_dir=kb_dir
    )

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(role=ChatRole.USER, content="Run a risk check on the book.")
            ]
        )
    )

    decision = response.decision
    assert decision is not None
    assert decision.recommendation.value == "escalate"
    assert decision.requires_approval is True
    assert decision.approval_id is not None
    approval = approvals_service.get_approval(decision.approval_id)
    assert approval is not None
    assert approval.status.value == "pending"
    assert approval.recommendation.value == "escalate"
    risk_ev = next(ev for ev in decision.evidence if ev.tool == "risk_check")
    assert risk_ev.data["status"] == "violations"
    assert decision.risk_level.value == "high"
    assert decision.confidence == 0.85
    # Approval record copies risk_level and confidence directly from the decision.
    assert approval.risk_level == "high"
    assert approval.confidence == 0.85


def test_trade_idea_pulls_market_quotes_for_mentioned_tickers(
    tmp_path: Path, kb_dir: Path
) -> None:
    csv = _write_clean_holdings(tmp_path)
    service, _ = _build_service(tmp_path=tmp_path, holdings_csv=csv, kb_dir=kb_dir)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="Should I buy NVDA today?",
                )
            ]
        )
    )

    decision = response.decision
    assert decision is not None
    assert decision.intent == "trade_idea"
    assert "market_quote" in response.used_tools
    quote_ev = next(ev for ev in decision.evidence if ev.tool == "market_quote")
    tickers = [q["ticker"] for q in quote_ev.data["quotes"]]
    assert "NVDA" in tickers
    assert decision.requires_approval is True
    assert decision.risk_level.value == "medium"
    assert decision.confidence == 0.65


def test_research_intent_retrieves_kb_citations(tmp_path: Path, kb_dir: Path) -> None:
    csv = _write_clean_holdings(tmp_path)
    service, _ = _build_service(tmp_path=tmp_path, holdings_csv=csv, kb_dir=kb_dir)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="What does the policy say about sector limits?",
                )
            ]
        )
    )

    assert "rag_retrieve" in response.used_tools
    assert response.citations, "expected at least one citation from KB"
    titles = {citation.title for citation in response.citations}
    policy_related_titles = {
        "policy.md",
        "investment_policy.md",
        "portfolio_committee_notes.md",
    }
    assert any(
        title in titles for title in policy_related_titles
    ) or any(title.endswith(".md") for title in titles)


def test_approval_not_created_when_decision_does_not_require_it(
    tmp_path: Path, kb_dir: Path
) -> None:
    csv = _write_clean_holdings(tmp_path)
    service, approvals_service = _build_service(
        tmp_path=tmp_path, holdings_csv=csv, kb_dir=kb_dir
    )

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(role=ChatRole.USER, content="Show me my portfolio exposure.")
            ]
        )
    )

    decision = response.decision
    assert decision is not None
    assert decision.requires_approval is False
    assert decision.approval_id is None
    assert approvals_service.list_approvals() == []
