"""Investigations service."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from alphalens.repositories.investigations import (
    InMemoryInvestigationRepository,
    InvestigationRepository,
)
from alphalens.schemas.agent import ChatAnswerType, ChatResponse, Recommendation
from alphalens.schemas.investigation import (
    InvestigationRecord,
    InvestigationStatus,
)

_INTENTS_THAT_ALWAYS_SAVE = {
    "portfolio_review",
    "portfolio_performance",
    "policy_breach_check",
    "investment_recommendation",
    "market_event_investigation",
    "macro_risk_review",
    "sec_filing_review",
    "rag_policy_question",
    "risk_review",
    "report_generation",
    "scenario_analysis",
    "scenario_simulation",
}

_SUBJECT_RE = re.compile(r"\b([A-Z]{2,5})\b")


class InvestigationsService:
    def __init__(self, repository: InvestigationRepository | None = None) -> None:
        self._repository = repository or InMemoryInvestigationRepository()

    def list_investigations(self, *, user_id: str) -> list[InvestigationRecord]:
        return self._repository.list(user_id=user_id)

    def get_investigation(self, investigation_id: str, *, user_id: str) -> InvestigationRecord | None:
        return self._repository.get(investigation_id, user_id=user_id)

    def delete_investigation(self, investigation_id: str, *, user_id: str) -> bool:
        return self._repository.delete(investigation_id, user_id=user_id)

    def update_status(
        self,
        investigation_id: str,
        *,
        user_id: str,
        status: InvestigationStatus,
    ) -> InvestigationRecord | None:
        existing = self._repository.get(investigation_id, user_id=user_id)
        if existing is None:
            return None
        updated = existing.model_copy(update={"status": status, "updated_at": datetime.now(tz=UTC)})
        return self._repository.update(updated)

    def create_from_chat_response(
        self,
        *,
        user_id: str,
        user_prompt: str,
        response: ChatResponse,
    ) -> InvestigationRecord | None:
        if response.answer_type != ChatAnswerType.INVESTMENT_DECISION:
            return None
        if not _should_create_investigation(user_prompt=user_prompt, response=response):
            return None
        now = datetime.now(tz=UTC)
        subject = _derive_subject(user_prompt=user_prompt, response=response)
        record = InvestigationRecord(
            id=f"inv_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            conversation_id=response.conversation_id,
            source_response_id=response.response_id,
            title=_derive_title(user_prompt=user_prompt, response=response, subject=subject),
            status=_default_status(response),
            intent=response.analysis.intent,
            subject=subject,
            created_at=now,
            updated_at=now,
            summary=response.analysis.final_answer.strip(),
            recommendation=response.analysis.recommendation,
            risk_level=response.decision.risk_level.value if response.decision is not None else None,
            confidence=response.analysis.confidence,
            tools_used=list(response.analysis.tools_used),
            evidence_items=[item.model_dump(mode="json") for item in response.analysis.evidence_items],
            rag_sources=[source.model_dump(mode="json") for source in response.analysis.rag_sources],
            provider_modes=[mode.model_dump(mode="json") for mode in response.analysis.provider_modes],
            data_used=list(response.analysis.data_used),
            orchestration_trace=dict(response.analysis.orchestration_trace),
            approval_id=response.decision.approval_id if response.decision is not None else None,
            report_id=None,
            limitations=list(response.analysis.limitations),
        )
        return self._repository.create(record)

    def reset(self) -> None:
        clear = getattr(self._repository, "clear", None)
        if callable(clear):
            clear()


def _should_create_investigation(*, user_prompt: str, response: ChatResponse) -> bool:
    if response.answer_type != ChatAnswerType.INVESTMENT_DECISION:
        return False
    rec = response.analysis.recommendation
    return bool(
        response.analysis.tools_used
        or response.analysis.rag_sources
        or (response.decision is not None and response.decision.approval_id)
        or rec not in {Recommendation.INFORM, Recommendation.HOLD}
        or response.analysis.intent in _INTENTS_THAT_ALWAYS_SAVE
        or any(
            key in (response.analysis.intent or "").lower()
            for key in ("portfolio", "policy", "market", "news", "macro", "sec", "rag", "risk", "report", "scenario")
        )
        or any(
            key in user_prompt.lower()
            for key in ("portfolio", "policy", "market", "news", "macro", "sec", "filing", "rag", "risk", "report", "scenario")
        )
    )


def _derive_subject(*, user_prompt: str, response: ChatResponse) -> str | None:
    match = _SUBJECT_RE.search(user_prompt.upper())
    if match:
        return match.group(1)
    intent = (response.analysis.intent or "").replace("_", " ").strip()
    return intent.title() if intent else None


def _derive_title(*, user_prompt: str, response: ChatResponse, subject: str | None) -> str:
    prompt = user_prompt.lower()
    if "trim" in prompt and subject:
        return f"{subject} trim review"
    if "policy" in prompt and ("breach" in prompt or "violat" in prompt):
        return "Portfolio policy breach review"
    if "performance" in prompt:
        return "Portfolio performance review"
    if any(k in prompt for k in ("drop", "drops", "fall", "falls", "shock", "what if", "what happens if")):
        if subject:
            return f"{subject} scenario shock review"
        return "Portfolio scenario shock review"
    if "rag" in prompt or "internal policy" in prompt:
        return "Internal policy RAG review"
    if any(k in prompt for k in ("market", "news")):
        if subject:
            return f"{subject} market news investigation"
        return "Market event investigation"
    if "macro" in prompt:
        return "Macro risk review"
    if "sec" in prompt or "filing" in prompt:
        return "SEC filing risk review"
    if subject:
        return f"{subject} investigation"
    intent = response.analysis.intent.replace("_", " ").strip()
    if intent:
        return f"{intent.title()} review"
    return "Investment investigation"


def _default_status(response: ChatResponse) -> InvestigationStatus:
    if response.decision and response.decision.recommendation == Recommendation.NEEDS_MORE_ANALYSIS:
        return InvestigationStatus.NEEDS_MORE_ANALYSIS
    return InvestigationStatus.OPEN

