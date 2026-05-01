"""Approval workflow service backed by an injected repository."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from alphalens.repositories.approvals import (
    ApprovalRepository,
    InMemoryApprovalRepository,
)
from alphalens.schemas.agent import AgentDecision, EvidenceItem, Recommendation
from alphalens.schemas.approval import (
    ApprovalActionType,
    ApprovalDecision,
    ApprovalRecord,
    ApprovalStatus,
)


class ApprovalsService:
    """Manage human approval records without executing external side effects."""

    def __init__(self, repository: ApprovalRepository | None = None) -> None:
        self._repository = repository or InMemoryApprovalRepository()

    def create_approval_from_decision(
        self,
        decision: AgentDecision,
        *,
        user_id: str,
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            approval_id=f"apv_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            action_type=_approval_action_type(decision.recommendation),
            asset=_extract_asset(decision.evidence),
            recommendation=decision.recommendation,
            rationale=_build_rationale(decision),
            evidence=list(decision.evidence),
            risk_level=decision.risk_level.value,
            confidence=decision.confidence,
        )
        return self._repository.create(record)

    def list_approvals(
        self,
        *,
        user_id: str,
        status: ApprovalStatus | None = None,
    ) -> list[ApprovalRecord]:
        return self._repository.list(user_id=user_id, status=status)

    def get_approval(self, approval_id: str, *, user_id: str) -> ApprovalRecord | None:
        return self._repository.get(approval_id, user_id=user_id)

    def decide_approval(
        self,
        approval_id: str,
        decision: ApprovalDecision,
        *,
        user_id: str,
    ) -> ApprovalRecord | None:
        record = self._repository.get(approval_id, user_id=user_id)
        if record is None:
            return None
        updated = record.model_copy(
            update={
                "status": decision.status,
                "reviewer_note": decision.reviewer_note,
                "decided_at": record.decided_at or _utcnow(),
            }
        )
        return self._repository.update(updated)

    def reset(self) -> None:
        clear = getattr(self._repository, "clear", None)
        if callable(clear):
            clear()


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(tz=UTC)


def _approval_action_type(recommendation: Recommendation) -> ApprovalActionType:
    mapping = {
        Recommendation.BUY: ApprovalActionType.BUY,
        Recommendation.SELL: ApprovalActionType.SELL,
        Recommendation.TRIM: ApprovalActionType.TRIM,
        Recommendation.REBALANCE: ApprovalActionType.REBALANCE,
        Recommendation.ESCALATE: ApprovalActionType.ESCALATE,
        Recommendation.NEEDS_MORE_ANALYSIS: ApprovalActionType.REPORT,
        Recommendation.HOLD: ApprovalActionType.REPORT,
        Recommendation.INFORM: ApprovalActionType.REPORT,
    }
    return mapping[recommendation]


def _build_rationale(decision: AgentDecision) -> str:
    if decision.reasoning:
        return " ".join(decision.reasoning)
    return f"Agent recommends {decision.recommendation.value}."


def _extract_asset(evidence: Iterable[EvidenceItem]) -> str | None:
    for item in evidence:
        data = item.data
        if not isinstance(data, dict):
            continue
        quotes = data.get("quotes")
        if isinstance(quotes, list) and quotes:
            quote = quotes[0]
            if isinstance(quote, dict) and quote.get("ticker"):
                return str(quote["ticker"])
        findings = data.get("findings")
        if isinstance(findings, list) and findings:
            finding = findings[0]
            if isinstance(finding, dict) and finding.get("subject"):
                return str(finding["subject"])
    return None

