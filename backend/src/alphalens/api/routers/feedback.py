"""Feedback endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import FeedbackServiceDep
from alphalens.schemas.feedback import FeedbackCreate, FeedbackRecord, FeedbackSummary

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackRecord)
def create_feedback(payload: FeedbackCreate, service: FeedbackServiceDep) -> FeedbackRecord:
    return service.create_feedback(payload)


@router.get("", response_model=list[FeedbackRecord])
def list_feedback(service: FeedbackServiceDep) -> list[FeedbackRecord]:
    return service.list_feedback()


@router.get("/summary", response_model=FeedbackSummary)
def get_feedback_summary(service: FeedbackServiceDep) -> FeedbackSummary:
    return service.summarize_feedback()
