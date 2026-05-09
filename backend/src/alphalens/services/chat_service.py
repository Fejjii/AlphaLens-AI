"""Chat service: orchestrates the agent graph for /agent/chat.

Wires real tools (portfolio, risk, market data, RAG) into the
LangGraph and shapes the output into the API contract. No LLM yet —
the responder applies deterministic rules.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
    ChatAnswerType,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    ChatRouting,
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
from alphalens.services.search_service import resolve_search_provider
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
from alphalens.schemas.llm import RouteClassification
from alphalens.schemas.user import UserProfile
from alphalens.services.chat_domain_router import (
    clarification_reply,
    resolve_chat_route,
)
from alphalens.services.app_help_replies import compose_app_help_reply
from alphalens.services.domain_gate import out_of_scope_reply
from alphalens.services.investigations_service import InvestigationsService

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
        investigations_service: InvestigationsService | None = None,
    ) -> None:
        self._settings = settings
        self._approvals_service = approvals_service
        self._usage_service = usage_service
        self._memory_service = memory_service
        self._investigations_service = investigations_service
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

        def _llm_route(msg: str) -> RouteClassification:
            return self._llm_service.classify_route(
                message=msg, conversation_id=conversation_id
            )

        route = resolve_chat_route(
            latest_user_text,
            prior_messages=prior_messages,
            detected_language=detected_language or "en",
            confidence_threshold=self._settings.chat_router_confidence_threshold,
            llm_classify=_llm_route if self._llm_service.using_llm else None,
        )
        if route.answer_type != ChatAnswerType.INVESTMENT_DECISION.value:
            gated = _build_gated_response(
                conversation_id=conversation_id,
                latest_user_text=latest_user_text,
                routing=route,
                response_language=response_language,
                detected_language=detected_language,
            )
            gated = _enforce_chat_response_contract(gated)
            stub_state: AgentState = {
                "conversation_id": conversation_id,
                "messages": merged_messages,
                "used_tools": [],
                "rag_requested": False,
                "needs_rag": False,
            }
            self._save_turn(
                conversation_id,
                user_id=user.id,
                request_messages=request_messages,
                response=gated,
                final_state=stub_state,
            )
            self._log_debug_trace(
                request_id=request_id,
                conversation_id=conversation_id,
                endpoint=endpoint,
                user_id=user.id,
                latest_user_text=latest_user_text,
                final_state=stub_state,
                response=gated,
            )
            _log_route_trace(
                settings=self._settings,
                request_id=request_id,
                conversation_id=conversation_id,
                latest_user_text=latest_user_text,
                prior_messages=prior_messages,
                route=route,
                langgraph_invoked=False,
                response=gated,
            )
            return gated

        initial_state: AgentState = {
            "conversation_id": conversation_id,
            "messages": merged_messages,
            "conversation_history": prior_messages,
            "previous_decisions": list(history.get("metadata", [])),
            "detected_language": detected_language,
            "response_language": response_language,
            "router_answer_type": route.answer_type,
            "router_intent": route.intent,
            "router_confidence": route.confidence,
            "router_reason": route.reason,
            "router_suggested_tools": list(route.suggested_tools),
            "router_language": route.language,
        }

        if self._settings.is_dev:
            log.info(
                "chat_langgraph_invoke",
                request_id=request_id or "n/a",
                conversation_id=conversation_id,
                user_id=user.id,
                domain_route_answer_type=route.answer_type,
                domain_route_intent=route.intent,
                domain_route_suggested_tools=list(route.suggested_tools),
                graph_input_suggested_tools=list(initial_state.get("router_suggested_tools", [])),
            )
        final_state: AgentState = self._graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": conversation_id}},
        )
        if self._settings.is_dev:
            log.info(
                "chat_langgraph_complete",
                request_id=request_id or "n/a",
                conversation_id=conversation_id,
                user_id=user.id,
                graph_intent=final_state.get("intent"),
                routing_intent=route.intent,
                routing_suggested_tools=list(route.suggested_tools),
                gather_selected_tools_before=list(final_state.get("gather_selected_tools_before", [])),
                gather_selected_tools_after=list(final_state.get("gather_selected_tools_after", [])),
                tools_executed=list(final_state.get("tools_executed", [])),
                tools_skipped=list(final_state.get("tools_skipped", [])),
                skip_reasons=list(final_state.get("skip_reasons", [])),
                graph_used_tools=list(final_state.get("used_tools", [])),
                evidence_count=len(final_state.get("evidence", [])),
            )
        response = _enforce_chat_response_contract(
            _to_response(
                conversation_id,
                final_state,
                domain_route=route,
                approvals_service=self._approvals_service,
                user_id=user.id,
            )
        )
        investigation = None
        if self._investigations_service is not None:
            try:
                investigation = self._investigations_service.create_from_chat_response(
                    user_id=user.id,
                    user_prompt=latest_user_text,
                    response=response,
                )
            except Exception as exc:
                if self._settings.is_dev:
                    log.warning(
                        "chat_investigation_create_failed",
                        request_id=request_id or "n/a",
                        conversation_id=conversation_id,
                        user_id=user.id,
                        error_type=exc.__class__.__name__,
                        error_message=str(exc)[:500],
                    )
                investigation = None
            if investigation is not None:
                response = response.model_copy(update={"investigation_id": investigation.id})
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
        _log_route_trace(
            settings=self._settings,
            request_id=request_id,
            conversation_id=conversation_id,
            latest_user_text=latest_user_text,
            prior_messages=prior_messages,
            route=route,
            langgraph_invoked=True,
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
        latest_user = next(
            (message for message in reversed(request_messages) if message.get("role") == ChatRole.USER.value),
            request_messages[-1],
        )
        created_at = datetime.now(tz=UTC).isoformat()
        user_message = {
            **latest_user,
            "metadata": {
                "created_at": created_at,
            },
        }
        assistant_metadata = {
            "created_at": created_at,
            "response_id": response.response_id,
            "answer_type": response.answer_type.value,
            "routing": response.routing.model_dump(mode="json"),
            "intent": response.analysis.intent,
            "tools_used": list(response.used_tools),
            "rag_sources": [source.model_dump(mode="json") for source in response.analysis.rag_sources],
            "provider_modes": [mode.model_dump(mode="json") for mode in response.analysis.provider_modes],
            "data_used": list(response.analysis.data_used),
            "limitations": list(response.analysis.limitations),
            "orchestration_trace": dict(response.analysis.orchestration_trace),
            "approval_id": response.decision.approval_id if response.decision is not None else None,
            "analysis": response.analysis.model_dump(mode="json"),
            "decision": response.decision.model_dump(mode="json") if response.decision is not None else None,
            "investigation_id": response.investigation_id,
        }
        assistant_message = {
            **response.message.model_dump(mode="json"),
            "metadata": assistant_metadata,
        }
        metadata = {
            "intent": final_state.get("intent") or response.analysis.intent,
            "recommendation": final_state.get("recommendation"),
            "used_tools": list(final_state.get("used_tools", [])),
            "decision": response.decision.model_dump(mode="json")
            if response.decision is not None
            else None,
            "created_at": created_at,
            "response_id": response.response_id,
            "answer_type": response.answer_type.value,
            "routing": response.routing.model_dump(mode="json"),
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


def _enforce_chat_response_contract(response: ChatResponse) -> ChatResponse:
    """Strip investment-only fields when the route is not investment_decision."""
    if response.answer_type == ChatAnswerType.INVESTMENT_DECISION:
        return response
    if response.decision is not None or response.used_tools:
        response = response.model_copy(update={"decision": None, "used_tools": []})
    trace = {
        k: v
        for k, v in response.analysis.orchestration_trace.items()
        if k in ("routing", "domain_router", "answer_type")
    }
    clean_analysis = response.analysis.model_copy(
        update={
            "tools_used": [],
            "provider_modes": [],
            "rag_sources": [],
            "evidence_items": [],
            "data_used": [],
            "portfolio_snapshot_used": None,
            "policy_rules_used": [],
            "rag_status": "not_requested",
            "retrieval_mode": "none",
            "approval_required": False,
            "approval_reason": None,
            "recommendation": Recommendation.INFORM,
            "limitations": [],
            "disclaimer": None,
            "orchestration_trace": trace,
        }
    )
    return response.model_copy(update={"analysis": clean_analysis})


def _prior_messages_preview(prior: list[dict[str, Any]], *, max_items: int = 2, chars: int = 120) -> str:
    parts: list[str] = []
    for msg in prior[-max_items:]:
        role = msg.get("role", "?")
        content = str(msg.get("content", ""))[:chars].replace("\n", " ")
        parts.append(f"{role}:{content}")
    return " | ".join(parts) if parts else ""


def _log_route_trace(
    *,
    settings: Settings,
    request_id: str | None,
    conversation_id: str,
    latest_user_text: str,
    prior_messages: list[dict[str, Any]],
    route: ChatRouting,
    langgraph_invoked: bool,
    response: ChatResponse | None = None,
) -> None:
    if not settings.is_dev:
        return
    decision = response.decision if response is not None else None
    log.info(
        "chat_route_trace",
        request_id=request_id or "n/a",
        conversation_id=conversation_id,
        latest_user_message=latest_user_text[:400],
        prior_messages_count=len(prior_messages),
        prior_message_preview=_prior_messages_preview(prior_messages),
        domain_route_answer_type=route.answer_type,
        domain_route_intent=route.intent,
        domain_route_confidence=route.confidence,
        domain_route_reason=(route.reason or "")[:300],
        domain_route_suggested_tools=list(route.suggested_tools),
        langgraph_invoked=langgraph_invoked,
        decision_created=decision is not None,
        approval_id_created=decision.approval_id if decision is not None else None,
        final_answer_preview=(response.analysis.final_answer[:280] if response is not None else ""),
        response_answer_type=(response.answer_type.value if response is not None else ""),
    )


def _build_gated_response(
    *,
    conversation_id: str,
    latest_user_text: str,
    routing: ChatRouting,
    response_language: str,
    detected_language: str | None,
) -> ChatResponse:
    response_id = f"msg_{uuid.uuid4().hex[:12]}"
    try:
        answer_type = ChatAnswerType(routing.answer_type)
    except ValueError:
        answer_type = ChatAnswerType.CLARIFICATION
    if answer_type == ChatAnswerType.APP_HELP:
        body = compose_app_help_reply(latest_user_text, response_language)
        intent_label = "app_help"
    elif answer_type == ChatAnswerType.OUT_OF_SCOPE:
        body = out_of_scope_reply(response_language)
        intent_label = "out_of_scope"
    else:
        body = clarification_reply(response_language)
        answer_type = ChatAnswerType.CLARIFICATION
        intent_label = "clarification"
    analysis = ChatAnalysis(
        intent=intent_label,
        final_answer=body,
        recommendation=Recommendation.INFORM,
        confidence=float(routing.confidence),
        approval_required=False,
        approval_reason=None,
        tools_used=[],
        provider_modes=[],
        evidence_items=[],
        rag_sources=[],
        rag_status="not_requested",
        retrieval_mode="none",
        portfolio_snapshot_used=None,
        policy_rules_used=[],
        data_freshness=None,
        data_used=[],
        limitations=[],
        disclaimer=None,
        orchestration_trace={
            "answer_type": answer_type.value,
            "domain_router": True,
            "routing": routing.model_dump(),
        },
    )
    return ChatResponse(
        conversation_id=conversation_id,
        response_id=response_id,
        message=ChatMessage(role=ChatRole.ASSISTANT, content=body),
        answer_type=answer_type,
        routing=routing,
        detected_language=detected_language,
        response_language=response_language,
        citations=[],
        used_tools=[],
        decision=None,
        analysis=analysis,
    )


def _build_checkpointer(*, enabled: bool) -> Any | None:
    if not enabled:
        return None
    try:
        from langgraph.checkpoint.memory import MemorySaver

        return MemorySaver()
    except Exception:
        return None


def _analysis_limitations(*, rag_chunks: list[dict[str, Any]], extra: list[str] | None = None) -> list[str]:
    lines = [
        LIMITATIONS_TEXT,
        "Benchmark performance requires external provider connectivity.",
    ]
    if rag_chunks:
        lines.insert(
            1,
            "RAG evidence reflects currently indexed internal documents only.",
        )
    for item in extra or []:
        if item and item not in lines:
            lines.append(item)
    return lines


def _to_response(
    conversation_id: str,
    state: AgentState,
    *,
    domain_route: ChatRouting,
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
        limitations=_analysis_limitations(
            rag_chunks=rag_chunks,
            extra=list(state.get("tool_limitations", [])),
        ),
        disclaimer=DISCLAIMER_TEXT,
        orchestration_trace={
            "intent_detected": decision.intent,
            "tools_selected": tools_used,
            "gather_selected_tools_before": list(state.get("gather_selected_tools_before", [])),
            "gather_selected_tools_after": list(state.get("gather_selected_tools_after", [])),
            "tools_executed": list(state.get("tools_executed", [])),
            "tools_skipped": list(state.get("tools_skipped", [])),
            "skip_reasons": list(state.get("skip_reasons", [])),
            "evidence_gathered": [item.title for item in evidence_items],
            "rag_retrieval_status": rag_status,
            "retrieval_mode": retrieval_mode,
            "synthesis_mode": "deterministic_fallback",
            "approval_gate_result": (
                f"approval required ({decision.approval_required_reason or 'policy gate'})"
                if decision.requires_approval
                else "no approval required"
            ),
            "routing": domain_route.model_dump(),
            "router_suggested_tools": list(domain_route.suggested_tools),
        },
    )
    return ChatResponse(
        conversation_id=conversation_id,
        response_id=response_id,
        message=ChatMessage(role=ChatRole.ASSISTANT, content=answer),
        answer_type=ChatAnswerType.INVESTMENT_DECISION,
        routing=domain_route,
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
    _, search_external_enabled = resolve_search_provider(settings)
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
            mode="real" if search_external_enabled else "fallback",
            reason=None
            if search_external_enabled
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
    rebuilt: list[dict[str, Any]] = []
    for ev in state.get("evidence", []):
        if ev.get("tool") != "rag_retrieve":
            continue
        data = ev.get("data")
        if not isinstance(data, dict) or data.get("chunks") is not None:
            continue
        if not data.get("chunk_id") and not data.get("source"):
            continue
        rebuilt.append(
            {
                "chunk_id": data.get("chunk_id", ""),
                "source": str(data.get("source", "knowledge")),
                "score": data.get("score"),
                "text": data.get("text") or "",
            }
        )
    return rebuilt
