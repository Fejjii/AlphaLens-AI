"""Approval repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import ApprovalRecordModel
from alphalens.schemas.agent import Recommendation
from alphalens.schemas.approval import (
    ApprovalActionType,
    ApprovalRecord,
    ApprovalStatus,
)


class ApprovalRepository(Protocol):
    def create(self, record: ApprovalRecord) -> ApprovalRecord: ...

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRecord]: ...

    def get(self, approval_id: str) -> ApprovalRecord | None: ...

    def update(self, record: ApprovalRecord) -> ApprovalRecord: ...


@dataclass(slots=True)
class InMemoryApprovalRepository(ApprovalRepository):
    _records: dict[str, ApprovalRecord] = field(default_factory=dict)

    def create(self, record: ApprovalRecord) -> ApprovalRecord:
        self._records[record.approval_id] = record
        return record

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRecord]:
        records = list(self._records.values())
        if status is not None:
            records = [record for record in records if record.status is status]
        return sorted(records, key=lambda record: record.created_at, reverse=True)

    def get(self, approval_id: str) -> ApprovalRecord | None:
        return self._records.get(approval_id)

    def update(self, record: ApprovalRecord) -> ApprovalRecord:
        self._records[record.approval_id] = record
        return record

    def clear(self) -> None:
        self._records.clear()


class SqlAlchemyApprovalRepository(ApprovalRepository):
    """SQLAlchemy-backed repository for approval records."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, record: ApprovalRecord) -> ApprovalRecord:
        with self._session_factory() as session:
            session.add(_to_model(record))
            session.commit()
        return record

    def list(self, status: ApprovalStatus | None = None) -> list[ApprovalRecord]:
        with self._session_factory() as session:
            query = session.query(ApprovalRecordModel)
            if status is not None:
                query = query.filter(ApprovalRecordModel.status == status.value)
            rows = query.order_by(ApprovalRecordModel.created_at.desc()).all()
            return [_to_schema(row) for row in rows]

    def get(self, approval_id: str) -> ApprovalRecord | None:
        with self._session_factory() as session:
            row = session.get(ApprovalRecordModel, approval_id)
            if row is None:
                return None
            return _to_schema(row)

    def update(self, record: ApprovalRecord) -> ApprovalRecord:
        with self._session_factory() as session:
            existing = session.get(ApprovalRecordModel, record.approval_id)
            if existing is None:
                session.add(_to_model(record))
            else:
                _update_model(existing, record)
            session.commit()
        return record


def _to_model(record: ApprovalRecord) -> ApprovalRecordModel:
    return ApprovalRecordModel(
        approval_id=record.approval_id,
        created_at=record.created_at,
        status=record.status.value,
        action_type=record.action_type.value,
        asset=record.asset,
        recommendation=record.recommendation.value,
        rationale=record.rationale,
        evidence=[item.model_dump(mode="json") for item in record.evidence],
        risk_level=record.risk_level,
        confidence=record.confidence,
        reviewer_note=record.reviewer_note,
        decided_at=record.decided_at,
    )


def _update_model(model: ApprovalRecordModel, record: ApprovalRecord) -> None:
    model.created_at = record.created_at
    model.status = record.status.value
    model.action_type = record.action_type.value
    model.asset = record.asset
    model.recommendation = record.recommendation.value
    model.rationale = record.rationale
    model.evidence = [item.model_dump(mode="json") for item in record.evidence]
    model.risk_level = record.risk_level
    model.confidence = record.confidence
    model.reviewer_note = record.reviewer_note
    model.decided_at = record.decided_at


def _to_schema(model: ApprovalRecordModel) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=model.approval_id,
        created_at=model.created_at,
        status=ApprovalStatus(model.status),
        action_type=ApprovalActionType(model.action_type),
        asset=model.asset,
        recommendation=Recommendation(model.recommendation),
        rationale=model.rationale,
        evidence=model.evidence,
        risk_level=model.risk_level,
        confidence=model.confidence,
        reviewer_note=model.reviewer_note,
        decided_at=model.decided_at,
    )
