"""Feedback repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from alphalens.schemas.feedback import FeedbackRecord


class FeedbackRepository(Protocol):
    def create(self, record: FeedbackRecord) -> FeedbackRecord: ...

    def list(self) -> list[FeedbackRecord]: ...


@dataclass(slots=True)
class InMemoryFeedbackRepository(FeedbackRepository):
    _records: dict[str, FeedbackRecord] = field(default_factory=dict)

    def create(self, record: FeedbackRecord) -> FeedbackRecord:
        self._records[record.id] = record
        return record

    def list(self) -> list[FeedbackRecord]:
        return sorted(self._records.values(), key=lambda record: record.created_at, reverse=True)

    def clear(self) -> None:
        self._records.clear()
