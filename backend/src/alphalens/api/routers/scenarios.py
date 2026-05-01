"""Scenario simulation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from alphalens.api.deps import CurrentUserDep, PlanServiceDep, ScenariosServiceDep
from alphalens.api.rate_limit import rate_limit_request
from alphalens.core.config import get_settings
from alphalens.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioSummary

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("", response_model=ScenarioResponse)
def create_scenario(
    request: Request,
    payload: ScenarioCreate,
    service: ScenariosServiceDep,
    current_user: CurrentUserDep,
    plans: PlanServiceDep,
) -> ScenarioResponse:
    plans.ensure_usage_allowed(current_user, "scenarios")
    rate_limit_request(request, route="scenarios", subject=current_user.id, settings=get_settings())
    return service.create_scenario(payload, user_id=current_user.id)


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(
    service: ScenariosServiceDep,
    current_user: CurrentUserDep,
) -> list[ScenarioResponse]:
    return service.list_scenarios(user_id=current_user.id)


@router.get("/summary", response_model=ScenarioSummary)
def get_summary(service: ScenariosServiceDep, current_user: CurrentUserDep) -> ScenarioSummary:
    return service.summarize_scenarios(user_id=current_user.id)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: str,
    service: ScenariosServiceDep,
    current_user: CurrentUserDep,
) -> ScenarioResponse:
    scenario = service.get_scenario(scenario_id, user_id=current_user.id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    return scenario
