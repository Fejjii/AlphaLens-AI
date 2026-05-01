"""Feedback endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from alphalens.api.deps import CurrentUserDep, FeedbackServiceDep
from alphalens.api.rate_limit import rate_limit_request
from alphalens.core.config import get_settings
from alphalens.schemas.feedback import FeedbackCreate, FeedbackRecord, FeedbackSummary

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackRecord)
def create_feedback(
    request: Request,
    payload: FeedbackCreate,
    service: FeedbackServiceDep,
    current_user: CurrentUserDep,
) -> FeedbackRecord:
    rate_limit_request(request, route="feedback", subject=current_user.id, settings=get_settings())
    return service.create_feedback(payload, user_id=current_user.id)


@router.get("", response_model=list[FeedbackRecord])
def list_feedback(
    service: FeedbackServiceDep,
    current_user: CurrentUserDep,
) -> list[FeedbackRecord]:
    return service.list_feedback(user_id=current_user.id)


@router.get("/summary", response_model=FeedbackSummary)
def get_feedback_summary(
    service: FeedbackServiceDep,
    current_user: CurrentUserDep,
) -> FeedbackSummary:
    return service.summarize_feedback(user_id=current_user.id)
