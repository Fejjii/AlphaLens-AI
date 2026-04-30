"""Report and memo generation schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import Field

from alphalens.schemas.agent import EvidenceItem
from alphalens.schemas.common import APIModel


class ReportType(str, Enum):
    INVESTMENT_MEMO = "investment_memo"
    RISK_REVIEW = "risk_review"
    PORTFOLIO_UPDATE = "portfolio_update"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"


class ReportSection(APIModel):
    key: str
    title: str
    content: str
    bullets: list[str] = Field(default_factory=list)


class ReportCreate(APIModel):
    title: str | None = None
    report_type: ReportType = ReportType.INVESTMENT_MEMO
    prompt: str = Field(..., min_length=3)
    conversation_id: str | None = None
    source_response_id: str | None = None
    ticker: str | None = None


class ReportResponse(APIModel):
    id: str
    title: str
    report_type: ReportType
    conversation_id: str | None = None
    source_response_id: str | None = None
    ticker: str | None = None
    status: ReportStatus = ReportStatus.GENERATED
    sections: list[ReportSection] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class ReportSummary(APIModel):
    total_reports: int
    generated_reports: int
    by_type: dict[str, int] = Field(default_factory=dict)
