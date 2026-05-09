"""Agent chat request/response schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from alphalens.schemas.common import APIModel


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatMessage(APIModel):
    role: ChatRole
    content: str = Field(..., min_length=1)


class Citation(APIModel):
    """A reference to a knowledge-base document supporting an answer."""

    source_id: str
    title: str
    url: str | None = None
    snippet: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)


class Recommendation(str, Enum):
    INFORM = "inform"
    HOLD = "hold"
    NEEDS_MORE_ANALYSIS = "needs_more_analysis"
    BUY = "buy"
    SELL = "sell"
    TRIM = "trim"
    REBALANCE = "rebalance"
    ESCALATE = "escalate"


class EvidenceItem(APIModel):
    """A single piece of evidence backing the agent's reasoning."""

    tool: str = Field(..., description="Tool name that produced this evidence.")
    summary: str
    data: Any | None = None


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentDecision(APIModel):
    intent: str
    recommendation: Recommendation
    reasoning: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    disclaimer: str | None = None
    limitations: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    approval_id: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    evidence_count: int = 0
    approval_required_reason: str | None = None
    policy_flags: list[str] = Field(default_factory=list)


class ProviderMode(APIModel):
    name: str
    mode: str
    reason: str | None = None


class RAGSource(APIModel):
    document_title: str
    chunk_id: str
    score: float = Field(ge=0.0, le=1.0)
    snippet: str
    source: str | None = None


class EvidenceSource(APIModel):
    title: str
    detail: str
    source_type: str = "tool"


class ChatAnalysis(APIModel):
    intent: str
    final_answer: str
    recommendation: Recommendation
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    approval_required: bool = False
    approval_reason: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    provider_modes: list[ProviderMode] = Field(default_factory=list)
    evidence_items: list[EvidenceSource] = Field(default_factory=list)
    rag_sources: list[RAGSource] = Field(default_factory=list)
    rag_status: str | None = None
    retrieval_mode: str | None = None
    portfolio_snapshot_used: str | None = None
    policy_rules_used: list[str] = Field(default_factory=list)
    data_freshness: str | None = None
    data_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
    orchestration_trace: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(APIModel):
    conversation_id: str | None = Field(
        default=None,
        description="Stable conversation key for LangGraph checkpointing.",
    )
    messages: list[ChatMessage] = Field(..., min_length=1)


class ChatAnswerType(str, Enum):
    """How the frontend should render this assistant turn."""

    INVESTMENT_DECISION = "investment_decision"
    APP_HELP = "app_help"
    OUT_OF_SCOPE = "out_of_scope"
    CLARIFICATION = "clarification"


class ChatRouting(APIModel):
    """Structured domain routing metadata for every chat response."""

    answer_type: str
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    language: str
    reason: str = Field(default="", max_length=720)
    suggested_tools: list[str] = Field(default_factory=list)
    router_source: str | None = Field(
        default=None,
        description="deterministic_guard | llm | llm_low_confidence | deterministic_fallback",
    )


class ChatResponse(APIModel):
    conversation_id: str
    response_id: str
    message: ChatMessage
    answer_type: ChatAnswerType = ChatAnswerType.INVESTMENT_DECISION
    routing: ChatRouting
    detected_language: str | None = None
    response_language: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    decision: AgentDecision | None = None
    analysis: ChatAnalysis
    investigation_id: str | None = None
