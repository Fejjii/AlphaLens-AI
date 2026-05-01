"""Feedback loop service."""

from __future__ import annotations

import uuid
from collections import Counter

from alphalens.repositories.feedback import FeedbackRepository, InMemoryFeedbackRepository
from alphalens.schemas.feedback import FeedbackCreate, FeedbackRecord, FeedbackSummary
from alphalens.services.usage_service import UsageService


class FeedbackService:
    def __init__(
        self,
        repository: FeedbackRepository | None = None,
        usage_service: UsageService | None = None,
    ) -> None:
        self._repository = repository or InMemoryFeedbackRepository()
        self._usage_service = usage_service

    def create_feedback(self, payload: FeedbackCreate, *, user_id: str) -> FeedbackRecord:
        record = FeedbackRecord(
            id=f"fdb_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            conversation_id=payload.conversation_id,
            message_id=payload.message_id,
            response_id=payload.response_id,
            rating=payload.rating,
            comment=payload.comment,
            category=payload.category,
        )
        created = self._repository.create(record)
        if self._usage_service is not None:
            self._usage_service.record_event(
                event_type="feedback_submitted",
                provider="frontend",
                user_id=user_id,
                conversation_id=record.conversation_id,
                metadata={
                    "feedback_id": record.id,
                    "rating": record.rating.value,
                    "category": record.category.value if record.category else None,
                },
            )
        return created

    def list_feedback(self, *, user_id: str) -> list[FeedbackRecord]:
        return self._repository.list(user_id=user_id)

    def summarize_feedback(self, *, user_id: str) -> FeedbackSummary:
        records = self._repository.list(user_id=user_id)
        ratings = Counter(record.rating.value for record in records)
        categories = Counter(
            record.category.value for record in records if record.category is not None
        )
        return FeedbackSummary(
            total_feedback=len(records),
            thumbs_up=ratings["thumbs_up"],
            thumbs_down=ratings["thumbs_down"],
            by_category=dict(sorted(categories.items())),
        )

    def reset(self) -> None:
        clear = getattr(self._repository, "clear", None)
        if callable(clear):
            clear()
