"""Usage tracking endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import CurrentUserDep, UsageServiceDep
from alphalens.schemas.usage import UsageEvent, UsageSummary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/events", response_model=list[UsageEvent])
def list_events(service: UsageServiceDep, current_user: CurrentUserDep) -> list[UsageEvent]:
    """Return all recorded usage events (LLM calls and tool invocations)."""
    return service.list_usage_events(user_id=current_user.id)


@router.get("/summary", response_model=UsageSummary)
def get_summary(service: UsageServiceDep, current_user: CurrentUserDep) -> UsageSummary:
    """Return aggregated usage totals (tokens, cost, call counts)."""
    return service.get_usage_summary(user_id=current_user.id)
