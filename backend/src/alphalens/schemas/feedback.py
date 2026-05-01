"""Feedback loop schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import Field

from alphalens.schemas.common import APIModel


class FeedbackRating(str, Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"


class FeedbackCategory(str, Enum):
    ACCURACY = "accuracy"
    USEFULNESS = "usefulness"
    CLARITY = "clarity"
    RISK = "risk"
    OTHER = "other"


class FeedbackCreate(APIModel):
    conversation_id: str
    message_id: str | None = None
    response_id: str | None = None
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)
    category: FeedbackCategory | None = None


class FeedbackRecord(APIModel):
    id: str
    user_id: str
    conversation_id: str
    message_id: str | None = None
    response_id: str | None = None
    rating: FeedbackRating
    comment: str | None = None
    category: FeedbackCategory | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class FeedbackSummary(APIModel):
    total_feedback: int
    thumbs_up: int
    thumbs_down: int
    by_category: dict[str, int] = Field(default_factory=dict)
