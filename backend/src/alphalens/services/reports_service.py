"""Reports and memo generation service."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from alphalens.compliance.policy import DISCLAIMER_TEXT, LIMITATIONS_TEXT, assess_compliance
from alphalens.core.logging import get_logger
from alphalens.memory.service import MemoryService
from alphalens.repositories.reports import InMemoryReportRepository, ReportRepository
from alphalens.schemas.agent import EvidenceItem
from alphalens.schemas.report import (
    ReportCreate,
    ReportGenerationMeta,
    ReportMemoContext,
    ReportResponse,
    ReportSection,
    ReportStatus,
    ReportSummary,
    ReportType,
    _strip_to_report_analysis,
    _strip_to_report_decision,
)
from alphalens.services.usage_service import UsageService

log = get_logger(__name__)


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
        memory_context, source_lookup_failed = self._resolve_memory_context(payload, user_id=user_id)
        memo_context = self._resolve_memo_context(payload=payload, memory_context=memory_context)
        evidence = self._resolve_evidence(memo_context)
        citations = self._resolve_citations(memo_context)
        sections, fallback_used = _build_sections(
            payload=payload,
            memo_context=memo_context,
            evidence=evidence,
            citations=citations,
        )
        meta = _build_generation_meta(
            sections=sections,
            memo_context=memo_context,
            fallback_used=fallback_used,
            evidence_count=len(evidence),
            source_lookup_failed=source_lookup_failed,
        )
        assessment = assess_compliance(
            recommendation=(memo_context.decision.recommendation if memo_context.decision else "inform") or "inform",
            risk_level=(memo_context.decision.risk_level if memo_context.decision else "low") or "low",
            confidence=float(
                memo_context.decision.confidence
                if memo_context.decision and memo_context.decision.confidence is not None
                else (0.8 if evidence else 0.4)
            ),
            evidence_count=len(evidence),
            ticker_supported=bool(payload.ticker or memo_context.ticker_or_subject),
        )
        report_request_id = f"rpt_req_{uuid.uuid4().hex[:10]}"
        if _is_dev():
            log.info(
                "report_generation_trace",
                report_request_id=report_request_id,
                source_response_id=payload.source_response_id,
                source_lookup_failed=source_lookup_failed,
                ticker_or_subject=(payload.ticker or memo_context.ticker_or_subject or "n/a"),
                input_has_decision=memo_context.decision is not None,
                input_has_final_answer=bool((memo_context.agent_final_answer or "").strip()),
                input_evidence_count=len(evidence),
                input_rag_source_count=len(memo_context.analysis.rag_sources) if memo_context.analysis else 0,
                input_tools_used=(memo_context.analysis.tools_used if memo_context.analysis else []),
                approval_id=(memo_context.decision.approval_id if memo_context.decision else None),
                generated_report_sections=[section.key for section in sections],
                fallback_used=fallback_used,
            )
        report = ReportResponse(
            id=report_id,
            user_id=user_id,
            title=title,
            report_type=payload.report_type,
            conversation_id=payload.conversation_id,
            source_response_id=payload.source_response_id,
            ticker=(payload.ticker or memo_context.ticker_or_subject).upper()
            if (payload.ticker or memo_context.ticker_or_subject)
            else None,
            status=ReportStatus.GENERATED,
            sections=sections,
            evidence=evidence,
            citations=citations,
            disclaimer=DISCLAIMER_TEXT,
            limitations=_merged_limitations(memo_context),
            evidence_count=len(evidence),
            policy_flags=assessment.policy_flags,
            approval_required_reason=assessment.approval_required_reason,
            memo_metadata=meta,
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
            generated_reports=sum(1 for report in reports if report.status == ReportStatus.GENERATED),
            by_type=dict(sorted(counts.items())),
        )

    def reset(self) -> None:
        clear = getattr(self._repository, "clear", None)
        if callable(clear):
            clear()

    def _default_title(self, payload: ReportCreate) -> str:
        context = (
            payload.ticker.upper()
            if payload.ticker
            else (payload.memo_context.ticker_or_subject.upper() if payload.memo_context and payload.memo_context.ticker_or_subject else "General")
        )
        return f"{payload.report_type.value.replace('_', ' ').title()} · {context}"

    def _resolve_memory_context(
        self, payload: ReportCreate, *, user_id: str
    ) -> tuple[dict[str, Any] | None, bool]:
        """Return (memory assistant context dict or None, source_lookup_failed).

        ``source_lookup_failed`` is True when ``source_response_id`` was provided but no
        matching assistant message was found in the user's conversation history.
        """
        if not payload.conversation_id or self._memory_service is None:
            return None, False
        history = self._memory_service.get_history(payload.conversation_id, user_id=user_id)
        messages = history.get("messages", [])
        if not isinstance(messages, list) or not messages:
            return None, bool(payload.source_response_id)
        if payload.source_response_id:
            for message in reversed(messages):
                if not isinstance(message, dict):
                    continue
                metadata = message.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                if metadata.get("response_id") == payload.source_response_id:
                    context: dict[str, Any] = {"assistant_metadata": metadata}
                    prompt = self._find_prompt_before_response(messages, payload.source_response_id)
                    if prompt:
                        context["user_prompt"] = prompt
                    return context, False
            return None, True
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            metadata = message.get("metadata")
            if isinstance(metadata, dict) and metadata.get("response_id"):
                return {"assistant_metadata": metadata}, False
        return None, False

    def _find_prompt_before_response(self, messages: list[dict[str, Any]], response_id: str) -> str | None:
        for idx in range(len(messages) - 1, -1, -1):
            message = messages[idx]
            if not isinstance(message, dict):
                continue
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            if metadata.get("response_id") != response_id:
                continue
            for j in range(idx - 1, -1, -1):
                prior = messages[j]
                if isinstance(prior, dict) and prior.get("role") == "user":
                    text = str(prior.get("content", "")).strip()
                    return text or None
        return None

    def _resolve_memo_context(
        self,
        *,
        payload: ReportCreate,
        memory_context: dict[str, Any] | None,
    ) -> ReportMemoContext:
        """Prefer explicit ``memo_context`` from the client; fill gaps from memory only."""
        merged: dict[str, Any] = {}
        if payload.memo_context is not None:
            merged.update(payload.memo_context.model_dump(mode="json", exclude_none=True))
        from_memory = memory_context.get("assistant_metadata") if isinstance(memory_context, dict) else None
        if isinstance(from_memory, dict):
            merged.setdefault("user_prompt", memory_context.get("user_prompt") if memory_context else None)
            analysis_blob = from_memory.get("analysis")
            if isinstance(analysis_blob, dict):
                fa = str(analysis_blob.get("final_answer", "")).strip() or None
                merged.setdefault("agent_final_answer", fa)
            merged.setdefault("answer_type", from_memory.get("answer_type"))
            merged.setdefault("decision", _strip_to_report_decision(from_memory.get("decision")))
            merged.setdefault("analysis", _strip_to_report_analysis(from_memory.get("analysis")))
            if payload.ticker:
                merged.setdefault("ticker_or_subject", payload.ticker)
        if merged.get("decision") is not None:
            merged["decision"] = _strip_to_report_decision(merged.get("decision"))
        if merged.get("analysis") is not None:
            merged["analysis"] = _strip_to_report_analysis(merged.get("analysis"))
        return ReportMemoContext.model_validate(merged)

    def _resolve_evidence(self, memo_context: ReportMemoContext) -> list[EvidenceItem]:
        decision = memo_context.decision
        if decision is None:
            return []
        return list(decision.key_evidence)

    def _resolve_citations(self, memo_context: ReportMemoContext) -> list[str]:
        analysis = memo_context.analysis
        if analysis is None:
            return []
        tools = [str(tool) for tool in analysis.tools_used if str(tool).strip()]
        return tools[:8]


def _build_sections(
    *,
    payload: ReportCreate,
    memo_context: ReportMemoContext,
    evidence: list[EvidenceItem],
    citations: list[str],
) -> tuple[list[ReportSection], bool]:
    decision = memo_context.decision
    analysis = memo_context.analysis
    ticker = (payload.ticker or memo_context.ticker_or_subject or "the portfolio").upper()
    prompt = (memo_context.user_prompt or payload.prompt).strip()
    final_answer = (memo_context.agent_final_answer or "").strip()

    evidence_lines = [f"{item.tool}: {item.summary}" for item in evidence[:8]]
    rag_sources = analysis.rag_sources if analysis else []
    rag_lines: list[str] = []
    for source in rag_sources[:5]:
        if not isinstance(source, dict):
            continue
        title = str(source.get("document_title") or source.get("source") or "internal document")
        snippet = " ".join(str(source.get("snippet", "")).split())
        rag_lines.append(f"{title}: {snippet[:150] + ('…' if len(snippet) > 150 else '')}")

    thesis_lines: list[str] = []
    if decision and decision.key_reasoning:
        thesis_lines.extend(decision.key_reasoning[:4])
    if rag_lines:
        thesis_lines.append("Internal policy evidence was retrieved from the knowledge base.")
    if analysis and analysis.data_used:
        thesis_lines.append(f"Data used: {', '.join(analysis.data_used[:3])}.")

    portfolio_lines: list[str] = []
    if analysis and analysis.portfolio_snapshot_used:
        portfolio_lines.append(f"Portfolio snapshot: {analysis.portfolio_snapshot_used}.")
    if any(item.tool == "portfolio_analyze" for item in evidence):
        portfolio_lines.append("Portfolio analytics evidence was included in this memo context.")
    if any(item.tool == "policy_rules" for item in evidence):
        portfolio_lines.append("Policy thresholds and rules were referenced in the decision evidence.")

    risk_lines: list[str] = []
    if decision and decision.risk_level:
        risk_lines.append(f"Risk level: {decision.risk_level}.")
    if decision and decision.policy_flags:
        risk_lines.append(f"Policy flags: {', '.join(decision.policy_flags)}.")
    if decision and decision.approval_required_reason:
        risk_lines.append(f"Approval reason: {decision.approval_required_reason}.")
    if analysis and analysis.limitations:
        risk_lines.extend(analysis.limitations[:2])

    recommendation = decision.recommendation if decision and decision.recommendation else "inform"
    approval_required = bool(decision.approval_required) if decision else False
    fallback_used = not bool(
        final_answer
        or evidence_lines
        or thesis_lines
        or (analysis and (analysis.tools_used or analysis.rag_sources))
    )

    if fallback_used:
        tools = ", ".join(analysis.tools_used[:5]) if analysis and analysis.tools_used else "none"
        rag_titles = ", ".join(line.split(":", 1)[0] for line in rag_lines) if rag_lines else "none"
        confidence_text = (
            f"{decision.confidence:.2f}" if decision and decision.confidence is not None else "n/a"
        )
        final_answer = final_answer or (
            f"Limited-context memo for {ticker}: action={recommendation}, confidence={confidence_text}, tools={tools}, rag_sources={rag_titles}."
        )

    sections = [
        ReportSection(
            key="executive_summary",
            title="Executive Summary",
            content=final_answer or f"Memo generated for {ticker} from available decision context.",
            bullets=[
                f"Prompt: {prompt}",
                f"Recommendation: {recommendation}",
                f"Approval required: {'yes' if approval_required else 'no'}",
                (
                    f"Confidence: {decision.confidence:.2f}"
                    if decision and decision.confidence is not None
                    else "Confidence: not provided"
                ),
            ],
        ),
        ReportSection(
            key="investment_thesis",
            title="Investment Thesis",
            content=(
                "Thesis is derived from the originating agent decision context."
                if thesis_lines
                else "Investment thesis is limited because structured reasoning was not provided."
            ),
            bullets=thesis_lines or ["Missing: key reasoning from the source decision."],
        ),
        ReportSection(
            key="key_evidence",
            title="Key Evidence",
            content=(
                "Evidence combines structured tool outputs and retrieved internal policy context."
                if (evidence_lines or rag_lines)
                else "Limited context memo: no structured evidence was linked to this report request."
            ),
            bullets=(evidence_lines + rag_lines)[:10] or ["Missing: evidence rows and RAG sources."],
        ),
        ReportSection(
            key="portfolio_impact",
            title="Portfolio Impact",
            content=(
                "Portfolio impact assessment reflects available portfolio and policy context."
                if portfolio_lines
                else "Portfolio impact could not be quantified from the provided context."
            ),
            bullets=portfolio_lines or ["Missing: portfolio snapshot or position-level analytics."],
        ),
        ReportSection(
            key="risk_assessment",
            title="Risk Assessment",
            content=(
                "Risk framing follows provided risk level, policy flags, and known limitations."
                if risk_lines
                else "Risk assessment is limited because risk metadata was not attached."
            ),
            bullets=risk_lines or ["Missing: risk level, policy flags, and approval rationale."],
        ),
        ReportSection(
            key="recommendation",
            title="Recommendation",
            content=f"Recommended action is '{recommendation}' for {ticker}.",
            bullets=[
                (
                    "Route this recommendation through human approval before execution."
                    if approval_required
                    else "No mandatory approval flag detected in this context."
                ),
                (
                    "This recommendation is constrained by partial context."
                    if fallback_used
                    else "Recommendation is grounded in linked decision evidence."
                ),
            ],
        ),
        ReportSection(
            key="required_approval_next_steps",
            title="Required Approval / Next Steps",
            content=(
                f"Approval ID: {decision.approval_id}."
                if decision and decision.approval_id
                else "No linked approval record was found for this report context."
            ),
            bullets=[
                f"Source context: {payload.source_response_id or 'manual request'}",
                (
                    f"Approval reason: {decision.approval_required_reason}"
                    if decision and decision.approval_required_reason
                    else "If execution is intended, submit through approvals workflow."
                ),
            ],
        ),
        ReportSection(
            key="limitations",
            title="Limitations",
            content=(
                "Limited context memo: some market or portfolio fields were unavailable."
                if fallback_used
                else "Memo grounded in available context; missing fields are noted in section bullets."
            ),
            bullets=[
                *(_safe_list(analysis.limitations[:3]) if analysis else []),
                f"Linked tools: {', '.join(citations) if citations else 'none'}",
            ],
        ),
        ReportSection(
            key="disclaimer",
            title="Disclaimer",
            content=DISCLAIMER_TEXT,
            bullets=["Decision support only.", "Not a recommendation to trade or execute."],
        ),
    ]
    return sections, fallback_used


def _build_generation_meta(
    *,
    sections: list[ReportSection],
    memo_context: ReportMemoContext,
    fallback_used: bool,
    evidence_count: int,
    source_lookup_failed: bool = False,
) -> ReportGenerationMeta:
    analysis = memo_context.analysis
    rag_count = len(analysis.rag_sources) if analysis else 0
    limited = fallback_used or evidence_count == 0
    return ReportGenerationMeta(
        limited_context=limited,
        rag_sources_count=rag_count,
        tools_used=list(analysis.tools_used) if analysis else [],
        fallback_used=fallback_used,
        generated_sections=[section.key for section in sections],
        approval_id=(memo_context.decision.approval_id if memo_context.decision else None),
        source_lookup_failed=source_lookup_failed,
    )


def _merged_limitations(memo_context: ReportMemoContext) -> list[str]:
    lines = [LIMITATIONS_TEXT, "This output is decision support, not financial advice."]
    if memo_context.analysis and memo_context.analysis.limitations:
        lines.extend(memo_context.analysis.limitations[:3])
    return list(dict.fromkeys(lines))


def _safe_list(items: list[str]) -> list[str]:
    return [item for item in items if isinstance(item, str) and item.strip()]


def _is_dev() -> bool:
    # config flag access is intentionally local to avoid threading settings through this service.
    from alphalens.core.config import get_settings

    return bool(get_settings().is_dev)
