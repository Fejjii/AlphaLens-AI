"""Investigation repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import InvestigationModel
from alphalens.schemas.agent import Recommendation
from alphalens.schemas.investigation import InvestigationRecord, InvestigationStatus


class InvestigationRepository(Protocol):
    def create(self, record: InvestigationRecord) -> InvestigationRecord: ...

    def list(self, *, user_id: str) -> list[InvestigationRecord]: ...

    def get(self, investigation_id: str, *, user_id: str) -> InvestigationRecord | None: ...

    def update(self, record: InvestigationRecord) -> InvestigationRecord: ...

    def delete(self, investigation_id: str, *, user_id: str) -> bool: ...


@dataclass(slots=True)
class InMemoryInvestigationRepository(InvestigationRepository):
    _records: dict[str, InvestigationRecord] = field(default_factory=dict)

    def create(self, record: InvestigationRecord) -> InvestigationRecord:
        self._records[record.id] = record
        return record

    def list(self, *, user_id: str) -> list[InvestigationRecord]:
        records = [record for record in self._records.values() if record.user_id == user_id]
        return sorted(records, key=lambda record: record.created_at, reverse=True)

    def get(self, investigation_id: str, *, user_id: str) -> InvestigationRecord | None:
        record = self._records.get(investigation_id)
        if record is None or record.user_id != user_id:
            return None
        return record

    def update(self, record: InvestigationRecord) -> InvestigationRecord:
        self._records[record.id] = record
        return record

    def delete(self, investigation_id: str, *, user_id: str) -> bool:
        existing = self._records.get(investigation_id)
        if existing is None or existing.user_id != user_id:
            return False
        del self._records[investigation_id]
        return True

    def clear(self) -> None:
        self._records.clear()


class SqlAlchemyInvestigationRepository(InvestigationRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, record: InvestigationRecord) -> InvestigationRecord:
        with self._session_factory() as session:
            session.add(_to_model(record))
            session.commit()
        return record

    def list(self, *, user_id: str) -> list[InvestigationRecord]:
        with self._session_factory() as session:
            rows = (
                session.query(InvestigationModel)
                .filter(InvestigationModel.user_id == user_id)
                .order_by(InvestigationModel.created_at.desc())
                .all()
            )
            return [_to_schema(row) for row in rows]

    def get(self, investigation_id: str, *, user_id: str) -> InvestigationRecord | None:
        with self._session_factory() as session:
            row = (
                session.query(InvestigationModel)
                .filter(InvestigationModel.id == investigation_id, InvestigationModel.user_id == user_id)
                .one_or_none()
            )
            return None if row is None else _to_schema(row)

    def update(self, record: InvestigationRecord) -> InvestigationRecord:
        with self._session_factory() as session:
            existing = (
                session.query(InvestigationModel)
                .filter(InvestigationModel.id == record.id, InvestigationModel.user_id == record.user_id)
                .one_or_none()
            )
            if existing is None:
                session.add(_to_model(record))
            else:
                _update_model(existing, record)
            session.commit()
        return record

    def delete(self, investigation_id: str, *, user_id: str) -> bool:
        with self._session_factory() as session:
            existing = (
                session.query(InvestigationModel)
                .filter(InvestigationModel.id == investigation_id, InvestigationModel.user_id == user_id)
                .one_or_none()
            )
            if existing is None:
                return False
            session.delete(existing)
            session.commit()
            return True


def _to_model(record: InvestigationRecord) -> InvestigationModel:
    return InvestigationModel(
        id=record.id,
        user_id=record.user_id,
        conversation_id=record.conversation_id,
        source_response_id=record.source_response_id,
        title=record.title,
        status=record.status.value,
        intent=record.intent,
        subject=record.subject,
        created_at=record.created_at,
        updated_at=record.updated_at,
        summary=record.summary,
        recommendation=record.recommendation.value,
        risk_level=record.risk_level,
        confidence=record.confidence,
        tools_used=list(record.tools_used),
        evidence_items=list(record.evidence_items),
        rag_sources=list(record.rag_sources),
        provider_modes=list(record.provider_modes),
        data_used=list(record.data_used),
        orchestration_trace=dict(record.orchestration_trace),
        approval_id=record.approval_id,
        report_id=record.report_id,
        limitations=list(record.limitations),
    )


def _update_model(model: InvestigationModel, record: InvestigationRecord) -> None:
    model.conversation_id = record.conversation_id
    model.source_response_id = record.source_response_id
    model.title = record.title
    model.status = record.status.value
    model.intent = record.intent
    model.subject = record.subject
    model.created_at = record.created_at
    model.updated_at = record.updated_at
    model.summary = record.summary
    model.recommendation = record.recommendation.value
    model.risk_level = record.risk_level
    model.confidence = record.confidence
    model.tools_used = list(record.tools_used)
    model.evidence_items = list(record.evidence_items)
    model.rag_sources = list(record.rag_sources)
    model.provider_modes = list(record.provider_modes)
    model.data_used = list(record.data_used)
    model.orchestration_trace = dict(record.orchestration_trace)
    model.approval_id = record.approval_id
    model.report_id = record.report_id
    model.limitations = list(record.limitations)


def _to_schema(model: InvestigationModel) -> InvestigationRecord:
    return InvestigationRecord(
        id=model.id,
        user_id=model.user_id,
        conversation_id=model.conversation_id,
        source_response_id=model.source_response_id,
        title=model.title,
        status=InvestigationStatus(model.status),
        intent=model.intent,
        subject=model.subject,
        created_at=model.created_at,
        updated_at=model.updated_at,
        summary=model.summary,
        recommendation=Recommendation(model.recommendation),
        risk_level=model.risk_level,
        confidence=model.confidence,
        tools_used=list(model.tools_used),
        evidence_items=list(model.evidence_items),
        rag_sources=list(model.rag_sources),
        provider_modes=list(model.provider_modes),
        data_used=list(model.data_used),
        orchestration_trace=dict(model.orchestration_trace or {}),
        approval_id=model.approval_id,
        report_id=model.report_id,
        limitations=list(model.limitations),
    )

