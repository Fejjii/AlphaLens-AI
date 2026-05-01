"""Chat service: orchestrates the agent graph for /agent/chat.

Wires real tools (portfolio, risk, market data, RAG) into the
LangGraph and shapes the output into the API contract. No LLM yet —
the responder applies deterministic rules.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from alphalens.agents.graph import build_graph
from alphalens.agents.state import AgentState
from alphalens.core.config import Settings
from alphalens.memory.service import MemoryService
from alphalens.services.language_service import get_response_language
from alphalens.schemas.agent import (
    AgentDecision,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    Citation,
    EvidenceItem,
    Recommendation,
    RiskLevel,
)
from alphalens.compliance.policy import DISCLAIMER_TEXT, LIMITATIONS_TEXT, assess_compliance
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.llm_service import LLMService, get_llm_service
from alphalens.services.macro_service import MacroService, get_macro_service
from alphalens.services.market_data_service import (
    MarketDataService,
    get_market_data_service,
)
from alphalens.services.rag_service import RAGService
from alphalens.services.search_service import SearchService, get_search_service
from alphalens.services.sec_service import SECService, get_sec_service
from alphalens.services.usage_service import UsageService
from alphalens.tools.macro_tool import make_macro_snapshot_tool
from alphalens.tools.market_data_tool import make_market_data_tool
from alphalens.tools.portfolio_tool import make_portfolio_tool
from alphalens.tools.rag_tool import make_rag_tool
from alphalens.tools.registry import ToolRegistry
from alphalens.tools.risk_tool import make_risk_tool
from alphalens.tools.sec_tool import make_sec_filings_tool
from alphalens.tools.web_search_tool import make_web_search_tool
from alphalens.schemas.user import UserProfile


def _resolve_holdings_path(settings: Settings) -> Path:
    """Mirror the KB-path resolution strategy for synthetic holdings.

    Defaults to `<repo>/data/synthetic/portfolio_holdings.csv`.
    """

    candidate = Path("data/synthetic/portfolio_holdings.csv")
    if candidate.is_absolute() and candidate.exists():
        return candidate
    if (Path.cwd() / candidate).exists():
        return Path.cwd() / candidate
    here = Path(__file__).resolve()
    for parent in here.parents:
        c = parent / candidate
        if c.exists():
            return c
    return Path.cwd() / candidate


def build_default_registry(
    *,
    settings: Settings,
    rag_service: RAGService,
    market_data_service: MarketDataService | None = None,
    search_service: SearchService | None = None,
    macro_service: MacroService | None = None,
    sec_service: SECService | None = None,
    usage_service: UsageService | None = None,
) -> ToolRegistry:
    registry = ToolRegistry(usage_service=usage_service)
    holdings_path = _resolve_holdings_path(settings)
    registry.register(make_portfolio_tool(holdings_path=holdings_path))
    registry.register(make_risk_tool(holdings_path=holdings_path))
    registry.register(
        make_market_data_tool(
            market_data_service or get_market_data_service(settings)
        )
    )
    registry.register(make_rag_tool(rag_service))
    registry.register(
        make_web_search_tool(search_service or get_search_service(settings))
    )
    registry.register(
        make_macro_snapshot_tool(macro_service or get_macro_service(settings))
    )
    registry.register(
        make_sec_filings_tool(sec_service or get_sec_service(settings))
    )
    return registry


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        rag_service: RAGService,
        approvals_service: ApprovalsService,
        registry: ToolRegistry | None = None,
        llm_service: LLMService | None = None,
        market_data_service: MarketDataService | None = None,
        search_service: SearchService | None = None,
        macro_service: MacroService | None = None,
        sec_service: SECService | None = None,
        usage_service: UsageService | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._settings = settings
        self._approvals_service = approvals_service
        self._usage_service = usage_service
        self._memory_service = memory_service
        self._registry = registry or build_default_registry(
            settings=settings,
            rag_service=rag_service,
            market_data_service=market_data_service,
            search_service=search_service,
            macro_service=macro_service,
            sec_service=sec_service,
            usage_service=usage_service,
        )
        self._llm_service = llm_service or get_llm_service(
            settings, usage_service=usage_service
        )
        self._graph = build_graph(
            self._registry,
            self._llm_service,
            checkpointer=_build_checkpointer(enabled=settings.memory_enabled),
        )

    def chat(self, request: ChatRequest, *, user: UserProfile | None = None) -> ChatResponse:
        user = user or _demo_user()
        conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        request_messages = [m.model_dump(mode="json") for m in request.messages]
        latest_user_text = next(
            (m.content for m in reversed(request.messages) if m.role == ChatRole.USER),
            "",
        )
        detected_language = get_response_language(
            latest_user_text, "auto", default_language="en"
        )
        response_language = get_response_language(
            latest_user_text, self._settings.default_response_language
            or "auto",
            default_language=detected_language,
        )
        history = self._memory_service.get_history(conversation_id, user_id=user.id) if self._memory_enabled else {
            "messages": [],
            "metadata": [],
        }
        prior_messages = list(history.get("messages", []))
        merged_messages = [*prior_messages, *request_messages]

        initial_state: AgentState = {
            "conversation_id": conversation_id,
            "messages": merged_messages,
            "conversation_history": prior_messages,
            "previous_decisions": list(history.get("metadata", [])),
            "detected_language": detected_language,
            "response_language": response_language,
        }

        final_state: AgentState = self._graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": conversation_id}},
        )
        response = _to_response(
            conversation_id,
            final_state,
            approvals_service=self._approvals_service,
            user_id=user.id,
        )
        self._save_turn(
            conversation_id,
            user_id=user.id,
            request_messages=request_messages,
            response=response,
            final_state=final_state,
        )
        return response

    @property
    def _memory_enabled(self) -> bool:
        return self._memory_service is not None and self._memory_service.enabled

    def get_memory(self, conversation_id: str, *, user_id: str | None = None) -> dict[str, Any]:
        user_id = user_id or "usr_demo"
        if not self._memory_enabled:
            return {"messages": [], "metadata": []}
        return self._memory_service.get_history(conversation_id, user_id=user_id)

    def clear_memory(self, conversation_id: str, *, user_id: str | None = None) -> None:
        user_id = user_id or "usr_demo"
        if not self._memory_enabled:
            return
        self._memory_service.clear(conversation_id, user_id=user_id)

    def _save_turn(
        self,
        conversation_id: str,
        *,
        user_id: str,
        request_messages: list[dict[str, Any]],
        response: ChatResponse,
        final_state: AgentState,
    ) -> None:
        if not self._memory_enabled or not request_messages:
            return
        user_message = request_messages[-1]
        assistant_message = response.message.model_dump(mode="json")
        metadata = {
            "intent": final_state.get("intent"),
            "recommendation": final_state.get("recommendation"),
            "used_tools": list(final_state.get("used_tools", [])),
            "decision": response.decision.model_dump(mode="json")
            if response.decision is not None
            else None,
        }
        self._memory_service.save_turn(
            conversation_id,
            user_id=user_id,
            user_message=user_message,
            assistant_message=assistant_message,
            metadata=metadata,
        )


def _build_checkpointer(*, enabled: bool) -> Any | None:
    if not enabled:
        return None
    try:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    except Exception:
        return None


def _to_response(
    conversation_id: str,
    state: AgentState,
    *,
    approvals_service: ApprovalsService,
    user_id: str,
) -> ChatResponse:
    response_id = f"msg_{uuid.uuid4().hex[:12]}"
    answer = state.get("answer") or "(no answer)"
    detected_language = state.get("detected_language")
    response_language = state.get("response_language")
    citations = [
        Citation(
            source_id=str(c.get("source_id", "")),
            title=str(c.get("title", "kb")),
            snippet=c.get("snippet"),
            score=c.get("score"),
        )
        for c in state.get("citations", [])
    ]
    decision = AgentDecision(
        intent=state.get("intent", "general"),
        recommendation=Recommendation(state.get("recommendation", "inform")),
        reasoning=list(state.get("reasoning", [])),
        evidence=[
            EvidenceItem(
                tool=str(ev.get("tool", "")),
                summary=str(ev.get("summary", "")),
                data=ev.get("data"),
            )
            for ev in state.get("evidence", [])
        ],
        requires_approval=bool(state.get("requires_approval", False)),
        risk_level=RiskLevel(state.get("risk_level", "low")),
        confidence=float(state.get("confidence", 0.7)),
        disclaimer=DISCLAIMER_TEXT,
        limitations=[LIMITATIONS_TEXT],
        evidence_count=len(state.get("evidence", [])),
    )
    assessment = assess_compliance(
        recommendation=decision.recommendation.value,
        risk_level=decision.risk_level.value,
        confidence=decision.confidence,
        evidence_count=decision.evidence_count,
        ticker_supported=_decision_supports_ticker(state),
        portfolio_impact=_portfolio_impact(state),
    )
    if assessment.recommendation_override is not None:
        decision.recommendation = Recommendation.NEEDS_MORE_ANALYSIS
    decision.requires_approval = decision.requires_approval or assessment.approval_required
    decision.approval_required_reason = assessment.approval_required_reason
    decision.policy_flags = assessment.policy_flags
    if decision.requires_approval:
        approval = approvals_service.create_approval_from_decision(decision, user_id=user_id)
        decision.approval_id = approval.approval_id
    return ChatResponse(
        conversation_id=conversation_id,
        response_id=response_id,
        message=ChatMessage(role=ChatRole.ASSISTANT, content=answer),
        detected_language=detected_language,
        response_language=response_language,
        citations=citations,
        used_tools=list(state.get("used_tools", [])),
        decision=decision,
    )


def _demo_user() -> UserProfile:
    return UserProfile(
        id="usr_demo",
        email="demo@alphalens.ai",
        full_name="Demo User",
        role="user",
        plan="free",
        is_active=True,
    )


def _decision_supports_ticker(state: AgentState) -> bool:
    recommendation = str(state.get("recommendation", "inform"))
    if recommendation in {"buy", "sell", "trim", "rebalance"}:
        return bool(state.get("used_tools"))
    return True


def _portfolio_impact(state: AgentState) -> float | None:
    impact = state.get("portfolio_impact")
    return float(impact) if isinstance(impact, (int, float)) else None
