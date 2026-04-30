"""Human-in-the-loop approval workflow schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import Field, field_validator

from alphalens.schemas.agent import EvidenceItem, Recommendation
from alphalens.schemas.common import APIModel


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_MORE_ANALYSIS = "needs_more_analysis"
    CANCELLED = "cancelled"


class ApprovalActionType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    TRIM = "trim"
    REBALANCE = "rebalance"
    ESCALATE = "escalate"
    REPORT = "report"


class ApprovalRecord(APIModel):
    approval_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    status: ApprovalStatus = ApprovalStatus.PENDING
    action_type: ApprovalActionType
    asset: str | None = None
    recommendation: Recommendation
    rationale: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    risk_level: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reviewer_note: str | None = None
    decided_at: datetime | None = None


class ApprovalDecision(APIModel):
    status: Literal[
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.NEEDS_MORE_ANALYSIS,
        ApprovalStatus.CANCELLED,
    ]
    reviewer_note: str | None = None

    @field_validator("reviewer_note")
    @classmethod
    def _normalize_reviewer_note(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value
