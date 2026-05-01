"""Feedback repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import FeedbackModel
from alphalens.schemas.feedback import FeedbackCategory, FeedbackRating, FeedbackRecord


class FeedbackRepository(Protocol):
    def create(self, record: FeedbackRecord) -> FeedbackRecord: ...

    def list(self, *, user_id: str) -> list[FeedbackRecord]: ...


@dataclass(slots=True)
class InMemoryFeedbackRepository(FeedbackRepository):
    _records: dict[str, FeedbackRecord] = field(default_factory=dict)

    def create(self, record: FeedbackRecord) -> FeedbackRecord:
        self._records[record.id] = record
        return record

    def list(self, *, user_id: str) -> list[FeedbackRecord]:
        records = [record for record in self._records.values() if record.user_id == user_id]
        return sorted(records, key=lambda record: record.created_at, reverse=True)

    def clear(self) -> None:
        self._records.clear()


class SqlAlchemyFeedbackRepository(FeedbackRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, record: FeedbackRecord) -> FeedbackRecord:
        with self._session_factory() as session:
            session.add(_to_model(record))
            session.commit()
        return record

    def list(self, *, user_id: str) -> list[FeedbackRecord]:
        with self._session_factory() as session:
            rows = (
                session.query(FeedbackModel)
                .filter(FeedbackModel.user_id == user_id)
                .order_by(FeedbackModel.created_at.desc())
                .all()
            )
            return [_to_schema(row) for row in rows]


def _to_model(record: FeedbackRecord) -> FeedbackModel:
    return FeedbackModel(
        id=record.id,
        user_id=record.user_id,
        conversation_id=record.conversation_id,
        message_id=record.message_id,
        response_id=record.response_id,
        rating=record.rating.value,
        comment=record.comment,
        category=record.category.value if record.category else None,
        created_at=record.created_at,
    )


def _to_schema(model: FeedbackModel) -> FeedbackRecord:
    return FeedbackRecord(
        id=model.id,
        user_id=model.user_id,
        conversation_id=model.conversation_id,
        message_id=model.message_id,
        response_id=model.response_id,
        rating=FeedbackRating(model.rating),
        comment=model.comment,
        category=FeedbackCategory(model.category) if model.category else None,
        created_at=model.created_at,
    )
