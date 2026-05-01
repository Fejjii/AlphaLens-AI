"""Reports and memo generation service."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from alphalens.memory.service import MemoryService
from alphalens.compliance.policy import DISCLAIMER_TEXT, LIMITATIONS_TEXT, assess_compliance
from alphalens.repositories.reports import InMemoryReportRepository, ReportRepository
from alphalens.schemas.agent import EvidenceItem
from alphalens.schemas.report import (
    ReportCreate,
    ReportResponse,
    ReportSection,
    ReportSummary,
    ReportType,
)
from alphalens.services.usage_service import UsageService


class ReportsService:
    def __init__(
        self,
        repository: ReportRepository | None = None,
        usage_service: UsageService | None = None,
        memory_service: MemoryService | None = None,
    ) -> None:
        self._repository = repository or InMemoryReportRepository()
        self._usage_service = usage_service
        self._memory_service = memory_service

    def create_report(self, payload: ReportCreate, *, user_id: str) -> ReportResponse:
        now = datetime.now(tz=UTC)
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"
        title = payload.title or self._default_title(payload)
        memory_context = self._resolve_memory_context(payload)
        evidence = self._resolve_evidence(memory_context)
        citations = self._resolve_citations(memory_context)
        sections = _build_sections(payload=payload, evidence=evidence, citations=citations)
        assessment = assess_compliance(
            recommendation="inform",
            risk_level="low",
            confidence=0.8 if evidence else 0.4,
            evidence_count=len(evidence),
            ticker_supported=bool(payload.ticker),
        )
        report = ReportResponse(
            id=report_id,
            user_id=user_id,
            title=title,
            report_type=payload.report_type,
            conversation_id=payload.conversation_id,
            source_response_id=payload.source_response_id,
            ticker=payload.ticker.upper() if payload.ticker else None,
            status="generated",
            sections=sections,
            evidence=evidence,
            citations=citations,
            disclaimer=DISCLAIMER_TEXT,
            limitations=[LIMITATIONS_TEXT, "This output is decision support, not financial advice."],
            evidence_count=len(evidence),
            policy_flags=assessment.policy_flags,
            approval_required_reason=assessment.approval_required_reason,
            created_at=now,
            updated_at=now,
        )
        created = self._repository.create(report)
        if self._usage_service is not None:
            self._usage_service.record_event(
                event_type="report_generated",
                provider="reports_service",
                user_id=user_id,
                conversation_id=payload.conversation_id,
                metadata={
                    "report_id": report_id,
                    "report_type": payload.report_type.value,
                    "source_response_id": payload.source_response_id,
                },
            )
        return created

    def list_reports(self, *, user_id: str) -> list[ReportResponse]:
        return self._repository.list(user_id=user_id)

    def get_report(self, report_id: str, *, user_id: str) -> ReportResponse | None:
        return self._repository.get(report_id, user_id=user_id)

    def summarize_reports(self, *, user_id: str) -> ReportSummary:
        reports = self._repository.list(user_id=user_id)
        counts = Counter(report.report_type.value for report in reports)
        return ReportSummary(
            total_reports=len(reports),
            generated_reports=sum(1 for report in reports if report.status == "generated"),
            by_type=dict(sorted(counts.items())),
        )

    def reset(self) -> None:
        clear = getattr(self._repository, "clear", None)
        if callable(clear):
            clear()

    def _default_title(self, payload: ReportCreate) -> str:
        context = payload.ticker.upper() if payload.ticker else "General"
        return f"{payload.report_type.value.replace('_', ' ').title()} · {context}"

    def _resolve_memory_context(self, payload: ReportCreate) -> dict[str, Any] | None:
        if not payload.conversation_id or self._memory_service is None:
            return None
        history = self._memory_service.get_history(payload.conversation_id)
        metadata = history.get("metadata", [])
        if not isinstance(metadata, list) or not metadata:
            return None
        return metadata[-1] if isinstance(metadata[-1], dict) else None

    def _resolve_evidence(self, memory_context: dict[str, Any] | None) -> list[EvidenceItem]:
        if not memory_context:
            return []
        decision = memory_context.get("decision")
        if not isinstance(decision, dict):
            return []
        evidence = decision.get("evidence")
        if not isinstance(evidence, list):
            return []
        return [EvidenceItem.model_validate(item) for item in evidence if isinstance(item, dict)]

    def _resolve_citations(self, memory_context: dict[str, Any] | None) -> list[str]:
        if not memory_context:
            return []
        used_tools = memory_context.get("used_tools")
        if isinstance(used_tools, list):
            return [str(tool) for tool in used_tools][:5]
        return []


def _build_sections(
    *,
    payload: ReportCreate,
    evidence: list[EvidenceItem],
    citations: list[str],
) -> list[ReportSection]:
    ticker = payload.ticker.upper() if payload.ticker else "the target asset"
    prompt = payload.prompt.strip()
    evidence_lines = [f"{item.tool}: {item.summary}" for item in evidence[:4]]
    if not evidence_lines:
        evidence_lines = [
            "No prior tool evidence was linked; this memo uses deterministic fallback framing."
        ]
    citation_lines = citations or ["No tool citations captured for this context."]
    return [
        ReportSection(
            key="disclaimer",
            title="Disclaimer",
            content=DISCLAIMER_TEXT,
            bullets=["Decision support only.", "Not a recommendation to trade or execute."],
        ),
        ReportSection(
            key="executive_summary",
            title="Executive Summary",
            content=f"This {payload.report_type.value.replace('_', ' ')} evaluates {ticker} based on: {prompt}",
            bullets=[
                f"Context: {prompt}",
                f"Memo type: {payload.report_type.value.replace('_', ' ')}",
            ],
        ),
        ReportSection(
            key="investment_thesis",
            title="Investment Thesis",
            content="The thesis is constructed from agent context and deterministic policy heuristics.",
            bullets=[
                "Assess directional opportunity versus downside asymmetry.",
                "Check consistency with portfolio mandate and concentration controls.",
            ],
        ),
        ReportSection(
            key="key_evidence",
            title="Key Evidence",
            content="Most relevant evidence items available at generation time.",
            bullets=evidence_lines,
        ),
        ReportSection(
            key="portfolio_impact",
            title="Portfolio Impact",
            content="Potential impact is estimated qualitatively for this MVP.",
            bullets=[
                "Review position size impact before any rebalance action.",
                "Validate correlation effects with existing holdings.",
            ],
        ),
        ReportSection(
            key="risk_assessment",
            title="Risk Assessment",
            content="Risk framing emphasizes concentration, liquidity, and model uncertainty.",
            bullets=[
                "Primary risk: thesis invalidation from new market data.",
                "Secondary risk: overfitting to limited context window.",
            ],
        ),
        ReportSection(
            key="recommendation",
            title="Recommendation",
            content=f"Recommendation remains informational pending explicit human review for {ticker}.",
            bullets=[
                "Treat as a draft memo for analyst review.",
                "Escalate if risk signals conflict with strategy limits.",
            ],
        ),
        ReportSection(
            key="required_approval_next_steps",
            title="Required Approval / Next Steps",
            content="No execution actions are taken by this report.",
            bullets=[
                "Route to human reviewer for sign-off.",
                f"Source context: {payload.source_response_id or 'manual request'}",
            ],
        ),
        ReportSection(
            key="limitations",
            title="Limitations",
            content="This MVP memo is deterministic and may omit real-time market nuance.",
            bullets=[
                "No live execution or trade routing.",
                f"Linked tool context: {', '.join(citation_lines)}",
                "This is not financial advice.",
            ],
        ),
    ]
