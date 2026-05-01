"""Plan and quota endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import CurrentUserDep, PlanServiceDep
from alphalens.schemas.plan import PlanResponse, PlanUsage

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse])
def list_plans(plans: PlanServiceDep) -> list[PlanResponse]:
    return plans.list_plans()


@router.get("/me", response_model=PlanResponse)
def get_my_plan(current_user: CurrentUserDep, plans: PlanServiceDep) -> PlanResponse:
    return plans.get_current_plan(current_user)


@router.get("/usage", response_model=PlanUsage)
def get_my_usage(current_user: CurrentUserDep, plans: PlanServiceDep) -> PlanUsage:
    return plans.usage(current_user)
