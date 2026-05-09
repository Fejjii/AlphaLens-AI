"""Report and memo generation schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator

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


class ReportDecisionContext(APIModel):
    action: str | None = None
    recommendation: str | None = None
    risk_level: str | None = None
    confidence: float | None = None
    approval_required: bool | None = None
    approval_id: str | None = None
    approval_required_reason: str | None = None
    key_reasoning: list[str] = Field(default_factory=list)
    key_evidence: list[EvidenceItem] = Field(default_factory=list)
    policy_flags: list[str] = Field(default_factory=list)

    @field_validator("key_evidence", mode="before")
    @classmethod
    def _normalize_key_evidence(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [_normalize_evidence_row(value)]


class ReportAnalysisContext(APIModel):
    intent: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    provider_modes: list[dict[str, Any]] = Field(default_factory=list)
    data_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    orchestration_trace: dict[str, Any] = Field(default_factory=dict)
    portfolio_snapshot_used: str | None = None
    policy_rules_used: list[str] = Field(default_factory=list)

    @field_validator("tools_used", mode="before")
    @classmethod
    def _normalize_tools_used(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            text = str(value).strip()
            return [text] if text else []
        return [str(item) for item in value if str(item).strip()]

    @field_validator("rag_sources", mode="before")
    @classmethod
    def _normalize_rag_sources(cls, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, dict):
            return [dict(value)]
        if not isinstance(value, list):
            return [
                {
                    "document_title": "unknown",
                    "source": "unknown",
                    "snippet": str(value),
                }
            ]
        rows: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                rows.append(dict(item))
            else:
                rows.append(
                    {
                        "document_title": "unknown",
                        "source": "unknown",
                        "snippet": str(item),
                    }
                )
        return rows


_ANALYSIS_FIELD_NAMES = frozenset(ReportAnalysisContext.model_fields.keys())
_DECISION_FIELD_NAMES = frozenset(ReportDecisionContext.model_fields.keys())


def _strip_to_report_analysis(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    return {k: v for k, v in raw.items() if k in _ANALYSIS_FIELD_NAMES}


def _normalize_evidence_row(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"tool": "unknown", "summary": str(item), "data": None}
    row = {k: v for k, v in item.items() if k in ("tool", "summary", "data")}
    if "tool" not in row or not str(row.get("tool", "")).strip():
        row["tool"] = "unknown"
    if "summary" not in row or not str(row.get("summary", "")).strip():
        row["summary"] = str(row.get("summary") or "(no summary)")
    return row


def _strip_to_report_decision(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    d = dict(raw)
    if "requires_approval" in d and "approval_required" not in d:
        d["approval_required"] = d.pop("requires_approval")
    if "reasoning" in d and "key_reasoning" not in d:
        d["key_reasoning"] = d.pop("reasoning")
    if "evidence" in d and "key_evidence" not in d:
        d["key_evidence"] = d.pop("evidence")
    d = {k: v for k, v in d.items() if k in _DECISION_FIELD_NAMES}
    ev = d.get("key_evidence")
    if isinstance(ev, list):
        d["key_evidence"] = [_normalize_evidence_row(x) for x in ev]
    return d


class ReportMemoContext(APIModel):
    user_prompt: str | None = None
    agent_final_answer: str | None = None
    answer_type: str | None = None
    decision: ReportDecisionContext | None = None
    analysis: ReportAnalysisContext | None = None
    ticker_or_subject: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_nested_memo_fields(cls, data: Any) -> Any:
        """Strip ChatAnalysis / AgentDecision extras so clients can forward API blobs safely."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if "analysis" in out:
            out["analysis"] = _strip_to_report_analysis(out.get("analysis"))
        if "decision" in out:
            out["decision"] = _strip_to_report_decision(out.get("decision"))
        return out


class ReportGenerationMeta(APIModel):
    limited_context: bool = False
    rag_sources_count: int = 0
    tools_used: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    generated_sections: list[str] = Field(default_factory=list)
    approval_id: str | None = None
    source_lookup_failed: bool = False


class ReportCreate(APIModel):
    title: str | None = None
    report_type: ReportType = ReportType.INVESTMENT_MEMO
    prompt: str = Field(..., min_length=3)
    conversation_id: str | None = None
    source_response_id: str | None = None
    ticker: str | None = None
    memo_context: ReportMemoContext | None = None

class ReportResponse(APIModel):
    id: str
    user_id: str
    title: str
    report_type: ReportType
    conversation_id: str | None = None
    source_response_id: str | None = None
    ticker: str | None = None
    status: ReportStatus = ReportStatus.GENERATED
    sections: list[ReportSection] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    disclaimer: str | None = None
    limitations: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    policy_flags: list[str] = Field(default_factory=list)
    approval_required_reason: str | None = None
    memo_metadata: ReportGenerationMeta = Field(default_factory=ReportGenerationMeta)
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class ReportSummary(APIModel):
    total_reports: int
    generated_reports: int
    by_type: dict[str, int] = Field(default_factory=dict)
