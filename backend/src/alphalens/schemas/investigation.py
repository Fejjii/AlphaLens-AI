"""Investigation persistence schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field

from alphalens.schemas.agent import Recommendation
from alphalens.schemas.common import APIModel


class InvestigationStatus(str, Enum):
    OPEN = "open"
    COMPLETED = "completed"
    NEEDS_MORE_ANALYSIS = "needs_more_analysis"
    APPROVED = "approved"
    REJECTED = "rejected"


class InvestigationRecord(APIModel):
    id: str
    user_id: str
    conversation_id: str
    source_response_id: str
    title: str
    status: InvestigationStatus = InvestigationStatus.OPEN
    intent: str
    subject: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    summary: str
    recommendation: Recommendation = Recommendation.INFORM
    risk_level: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    tools_used: list[str] = Field(default_factory=list)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    provider_modes: list[dict[str, Any]] = Field(default_factory=list)
    data_used: list[str] = Field(default_factory=list)
    orchestration_trace: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = None
    report_id: str | None = None
    limitations: list[str] = Field(default_factory=list)


class InvestigationStatusUpdate(APIModel):
    status: InvestigationStatus

