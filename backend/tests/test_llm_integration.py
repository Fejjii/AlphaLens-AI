"""Tests for the optional OpenAI LLM integration and deterministic fallback."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from alphalens.core.config import Settings
from alphalens.integrations.llm import (
    DeterministicFallbackLLMClient,
    LLMClient,
    LLMError,
)
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.schemas.llm import DecisionSynthesis, IntentClassification
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.llm_service import LLMService, get_llm_client, get_llm_service
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
    *, tmp_path: Path, kb_dir: Path, llm_service: LLMService
) -> ChatService:
    csv = _write_clean_holdings(tmp_path)
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"llm_test_{tmp_path.name}",
    )
    rag_service = RAGService(settings)
    registry = ToolRegistry()
    registry.register(make_portfolio_tool(holdings_path=csv))
    registry.register(make_risk_tool(holdings_path=csv))
    registry.register(make_market_data_tool(get_market_data_service(settings)))
    registry.register(make_rag_tool(rag_service))
    return ChatService(
        settings=settings,
        rag_service=rag_service,
        approvals_service=ApprovalsService(),
        registry=registry,
        llm_service=llm_service,
    )


# ---------------------------------------------------------------------------
# 1. No API key -> fallback client is selected
# ---------------------------------------------------------------------------


def test_no_api_key_uses_fallback_client() -> None:
    settings = Settings(openai_api_key=None, llm_enabled=True)

    primary = get_llm_client(settings)
    service = get_llm_service(settings)

    assert primary is None
    assert service.using_llm is False


def test_llm_disabled_uses_fallback_even_with_api_key() -> None:
    settings = Settings(openai_api_key="sk-test", llm_enabled=False)

    assert get_llm_client(settings) is None
    assert get_llm_service(settings).using_llm is False


# ---------------------------------------------------------------------------
# 2. Fallback preserves existing deterministic agent behavior
# ---------------------------------------------------------------------------


def test_fallback_preserves_existing_agent_behavior(
    tmp_path: Path, kb_dir: Path
) -> None:
    fallback_only = LLMService(primary=None, fallback=DeterministicFallbackLLMClient())
    service = _build_chat_service(
        tmp_path=tmp_path, kb_dir=kb_dir, llm_service=fallback_only
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
    assert decision.intent == "portfolio_review"
    assert "portfolio_analyze" in response.used_tools
    assert "risk_check" in response.used_tools
    assert decision.reasoning, "deterministic reasoning should be non-empty"


# ---------------------------------------------------------------------------
# 3. Mocked OpenAI classification drives tool selection
# ---------------------------------------------------------------------------


class _StubLLMClient(LLMClient):
    """Test double: returns canned classification + synthesis."""

    def __init__(
        self,
        *,
        classification: IntentClassification,
        synthesis: DecisionSynthesis | None = None,
        raise_on_classify: bool = False,
        raise_on_synthesize: bool = False,
    ) -> None:
        self._classification = classification
        self._synthesis = synthesis or DecisionSynthesis(
            reasoning=["llm-augmented reasoning"], summary="ok"
        )
        self._raise_on_classify = raise_on_classify
        self._raise_on_synthesize = raise_on_synthesize
        self.classify_calls = 0
        self.synthesize_calls = 0

    def classify_intent(self, *, message: str) -> IntentClassification:
        self.classify_calls += 1
        if self._raise_on_classify:
            raise LLMError("boom")
        return self._classification

    def synthesize_decision(
        self,
        *,
        intent: str,
        recommendation: str,
        evidence: list[dict],
        deterministic_reasoning: list[str],
    ) -> DecisionSynthesis:
        self.synthesize_calls += 1
        if self._raise_on_synthesize:
            raise LLMError("boom")
        return self._synthesis


def test_mocked_openai_classification_drives_tool_selection(
    tmp_path: Path, kb_dir: Path
) -> None:
    # Even though the user message is unambiguous research-style, the stub
    # forces a `risk_check` classification: gather must follow the LLM hints.
    stub = _StubLLMClient(
        classification=IntentClassification(
            intent="risk_check",
            tickers=[],
            needs_market_data=False,
            needs_rag=False,
            needs_portfolio=True,
            needs_risk_check=True,
        ),
    )
    llm = LLMService(primary=stub, fallback=DeterministicFallbackLLMClient())
    service = _build_chat_service(tmp_path=tmp_path, kb_dir=kb_dir, llm_service=llm)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="Tell me anything about the policy.",
                )
            ]
        )
    )

    assert stub.classify_calls == 1
    assert stub.synthesize_calls == 1
    assert response.decision is not None
    assert response.decision.intent == "risk_check"
    # LLM said no RAG / no market data — those tools must NOT have run.
    assert "rag_retrieve" not in response.used_tools
    assert "market_quote" not in response.used_tools
    # LLM-augmented reasoning is propagated through the synthesizer.
    assert "llm-augmented reasoning" in response.decision.reasoning


# ---------------------------------------------------------------------------
# 4. OpenAI error -> falls back cleanly without crashing
# ---------------------------------------------------------------------------


def test_openai_error_falls_back_cleanly(tmp_path: Path, kb_dir: Path) -> None:
    failing = _StubLLMClient(
        classification=IntentClassification(intent="ignored"),
        raise_on_classify=True,
        raise_on_synthesize=True,
    )
    llm = LLMService(primary=failing, fallback=DeterministicFallbackLLMClient())
    service = _build_chat_service(tmp_path=tmp_path, kb_dir=kb_dir, llm_service=llm)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(role=ChatRole.USER, content="Show me my portfolio exposure.")
            ]
        )
    )

    decision = response.decision
    assert decision is not None
    # Fallback ran, so we get the keyword-derived intent rather than the
    # stub's "ignored" placeholder.
    assert decision.intent == "portfolio_review"
    assert decision.reasoning, "fallback must still produce reasoning"


# ---------------------------------------------------------------------------
# 5. /agent/chat still returns AgentDecision regardless of LLM availability
# ---------------------------------------------------------------------------


async def test_agent_chat_endpoint_returns_decision(client: AsyncClient) -> None:
    payload = {"messages": [{"role": "user", "content": "How is my portfolio doing?"}]}
    response = await client.post("/agent/chat", json=payload)

    assert response.status_code == 200
    body = response.json()
    decision = body["decision"]
    assert decision is not None
    assert "intent" in decision
    assert "recommendation" in decision
    assert "risk_level" in decision
    assert "confidence" in decision
