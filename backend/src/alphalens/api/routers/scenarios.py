"""Scenario simulation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from alphalens.api.deps import ScenariosServiceDep
from alphalens.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioSummary

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post("", response_model=ScenarioResponse)
def create_scenario(payload: ScenarioCreate, service: ScenariosServiceDep) -> ScenarioResponse:
    return service.create_scenario(payload)


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(service: ScenariosServiceDep) -> list[ScenarioResponse]:
    return service.list_scenarios()


@router.get("/summary", response_model=ScenarioSummary)
def get_summary(service: ScenariosServiceDep) -> ScenarioSummary:
    return service.summarize_scenarios()


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(scenario_id: str, service: ScenariosServiceDep) -> ScenarioResponse:
    scenario = service.get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario_id}' not found.",
        )
    return scenario
