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
    requires_approval: bool = False
    approval_id: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ChatRequest(APIModel):
    conversation_id: str | None = Field(
        default=None,
        description="Stable conversation key for LangGraph checkpointing.",
    )
    messages: list[ChatMessage] = Field(..., min_length=1)


class ChatResponse(APIModel):
    conversation_id: str
    response_id: str
    message: ChatMessage
    detected_language: str | None = None
    response_language: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    decision: AgentDecision | None = None
