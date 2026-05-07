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
from alphalens.core.config import Settings, get_settings
from alphalens.core.logging import get_logger
from alphalens.memory.service import MemoryService
from alphalens.services.language_service import get_response_language
from alphalens.schemas.agent import (
    AgentDecision,
    ChatAnalysis,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    Citation,
    EvidenceItem,
    EvidenceSource,
    ProviderMode,
    RAGSource,
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

log = get_logger(__name__)


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

    def chat(
        self,
        request: ChatRequest,
        *,
        user: UserProfile | None = None,
        request_id: str | None = None,
        endpoint: str = "/agent/chat",
    ) -> ChatResponse:
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
        self._log_debug_trace(
            request_id=request_id,
            conversation_id=conversation_id,
            endpoint=endpoint,
            user_id=user.id,
            latest_user_text=latest_user_text,
            final_state=final_state,
            response=response,
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

    def _log_debug_trace(
        self,
        *,
        request_id: str | None,
        conversation_id: str,
        endpoint: str,
        user_id: str | None,
        latest_user_text: str,
        final_state: AgentState,
        response: ChatResponse,
    ) -> None:
        if not self._settings.is_dev:
            return
        rag_sources = response.analysis.rag_sources
        provider_mode = "openai" if self._llm_service.using_llm else "deterministic_fallback"
        log.info(
            "chat_debug_trace",
            request_id=request_id or "n/a",
            conversation_id=conversation_id,
            user_id=user_id or "anonymous",
            received_message=latest_user_text[:300],
            endpoint=endpoint,
            detected_intent=response.analysis.intent,
            selected_tools=list(response.analysis.tools_used),
            rag_requested=bool(final_state.get("rag_requested") or final_state.get("needs_rag")),
            rag_chunks_count=len(rag_sources),
            final_answer_preview=response.analysis.final_answer[:300],
            provider_mode=provider_mode,
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
        intent=state.get("intent", "general_question"),
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
    rag_chunks = _rag_chunks(state)
    rag_used = "rag_retrieve" in state.get("used_tools", [])
    rag_requested = bool(state.get("rag_requested") or state.get("needs_rag"))
    rag_unavailable = _provider_mode("Qdrant", "fallback") != "connected"
    rag_status = _rag_status(
        rag_chunks=rag_chunks,
        rag_used=rag_used,
        rag_requested=rag_requested,
        rag_unavailable=rag_unavailable,
    )
    retrieval_mode = _retrieval_mode(rag_chunks=rag_chunks)
    evidence_items = [
        EvidenceSource(
            title=str(ev.get("tool", "tool")),
            detail=str(ev.get("summary", "")),
            source_type="tool",
        )
        for ev in state.get("evidence", [])
    ]
    tools_used = list(state.get("used_tools", []))
    provider_modes = _provider_modes()
    analysis = ChatAnalysis(
        intent=decision.intent,
        final_answer=answer,
        recommendation=decision.recommendation,
        confidence=decision.confidence,
        approval_required=decision.requires_approval,
        approval_reason=decision.approval_required_reason,
        tools_used=tools_used,
        provider_modes=provider_modes,
        evidence_items=evidence_items,
        rag_sources=[
            RAGSource(
                document_title=str(chunk.get("source", "knowledge")),
                chunk_id=str(chunk.get("chunk_id", "")),
                score=float(chunk.get("score", 0.0)),
                snippet=str(chunk.get("text", ""))[:320],
                source=str(chunk.get("source", "")),
            )
            for chunk in rag_chunks
        ],
        rag_status=rag_status,
        retrieval_mode=retrieval_mode,
        portfolio_snapshot_used="synthetic_portfolio_holdings.csv",
        policy_rules_used=list(decision.policy_flags),
        data_freshness="Synthetic snapshot generated at request time.",
        data_used=_data_used_summary(
            tools_used=tools_used,
            rag_chunks=rag_chunks,
            provider_modes=provider_modes,
        ),
        limitations=[LIMITATIONS_TEXT, "Benchmark performance requires external provider connectivity."],
        disclaimer=DISCLAIMER_TEXT,
        orchestration_trace={
            "intent_detected": decision.intent,
            "tools_selected": tools_used,
            "evidence_gathered": [item.title for item in evidence_items],
            "rag_retrieval_status": rag_status,
            "retrieval_mode": retrieval_mode,
            "synthesis_mode": "deterministic_fallback",
            "approval_gate_result": (
                f"approval required ({decision.approval_required_reason or 'policy gate'})"
                if decision.requires_approval
                else "no approval required"
            ),
        },
    )
    return ChatResponse(
        conversation_id=conversation_id,
        response_id=response_id,
        message=ChatMessage(role=ChatRole.ASSISTANT, content=answer),
        detected_language=detected_language,
        response_language=response_language,
        citations=citations,
        used_tools=list(state.get("used_tools", [])),
        decision=decision,
        analysis=analysis,
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


def _provider_modes() -> list[ProviderMode]:
    settings = get_settings()
    return [
        ProviderMode(
            name="OpenAI LLM",
            mode="real" if settings.llm_enabled and bool(settings.openai_api_key) else "fallback",
            reason=None
            if settings.llm_enabled and settings.openai_api_key
            else "OPENAI_API_KEY not configured",
        ),
        ProviderMode(
            name="Market Data",
            mode="real"
            if settings.market_data_provider == "alpha_vantage"
            and bool(settings.alpha_vantage_api_key)
            else "fallback",
            reason=None
            if settings.market_data_provider == "alpha_vantage" and settings.alpha_vantage_api_key
            else "ALPHA_VANTAGE_API_KEY not configured",
        ),
        ProviderMode(
            name="Web/News",
            mode="real" if settings.search_provider == "serper" and bool(settings.serper_api_key) else "fallback",
            reason=None
            if settings.search_provider == "serper" and settings.serper_api_key
            else "SERPER_API_KEY not configured",
        ),
        ProviderMode(
            name="Qdrant",
            mode="connected" if settings.qdrant_url else "fallback",
            reason=None if settings.qdrant_url else "QDRANT_URL not configured",
        ),
    ]


def _provider_mode(name: str, fallback: str) -> str:
    for mode in _provider_modes():
        if mode.name == name:
            return mode.mode
    return fallback


def _rag_status(
    *,
    rag_chunks: list[dict[str, Any]],
    rag_used: bool,
    rag_requested: bool,
    rag_unavailable: bool,
) -> str:
    if rag_chunks:
        return "used"
    if rag_unavailable:
        return "unavailable"
    if rag_used or rag_requested:
        return "no_results"
    return "not_requested"


def _retrieval_mode(*, rag_chunks: list[dict[str, Any]]) -> str:
    if not rag_chunks:
        return "none"
    scores = [chunk.get("score") for chunk in rag_chunks if isinstance(chunk.get("score"), (int, float))]
    if not scores:
        return "unknown"
    return "qdrant" if any(float(score) > 0.0 for score in scores) else "lexical_fallback"


def _data_used_summary(
    *,
    tools_used: list[str],
    rag_chunks: list[dict[str, Any]],
    provider_modes: list[ProviderMode],
) -> list[str]:
    items: list[str] = []
    if tools_used:
        items.append(f"Tool outputs: {', '.join(tools_used)}")
    if rag_chunks:
        items.append(f"RAG chunks: {len(rag_chunks)}")
    fallback_modes = [m.name for m in provider_modes if m.mode in {"fallback", "disconnected", "memory_fallback"}]
    if fallback_modes:
        items.append(f"Fallback providers: {', '.join(fallback_modes)}")
    return items


def _rag_chunks(state: AgentState) -> list[dict[str, Any]]:
    for ev in state.get("evidence", []):
        if ev.get("tool") != "rag_retrieve":
            continue
        data = ev.get("data")
        if isinstance(data, dict) and isinstance(data.get("chunks"), list):
            return [item for item in data["chunks"] if isinstance(item, dict)]
    return []
