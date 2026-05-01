"""Scenario repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import ScenarioModel
from alphalens.schemas.scenario import ScenarioImpactItem, ScenarioResponse, ScenarioType


class ScenarioRepository(Protocol):
    def create(self, scenario: ScenarioResponse) -> ScenarioResponse: ...

    def list(self, *, user_id: str) -> list[ScenarioResponse]: ...

    def get(self, scenario_id: str, *, user_id: str) -> ScenarioResponse | None: ...


@dataclass(slots=True)
class InMemoryScenarioRepository(ScenarioRepository):
    _records: dict[str, ScenarioResponse] = field(default_factory=dict)

    def create(self, scenario: ScenarioResponse) -> ScenarioResponse:
        self._records[scenario.id] = scenario
        return scenario

    def list(self, *, user_id: str) -> list[ScenarioResponse]:
        records = [item for item in self._records.values() if item.user_id == user_id]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get(self, scenario_id: str, *, user_id: str) -> ScenarioResponse | None:
        scenario = self._records.get(scenario_id)
        if scenario is None or scenario.user_id != user_id:
            return None
        return scenario

    def clear(self) -> None:
        self._records.clear()


class SqlAlchemyScenarioRepository(ScenarioRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, scenario: ScenarioResponse) -> ScenarioResponse:
        with self._session_factory() as session:
            session.add(_to_model(scenario))
            session.commit()
        return scenario

    def list(self, *, user_id: str) -> list[ScenarioResponse]:
        with self._session_factory() as session:
            rows = (
                session.query(ScenarioModel)
                .filter(ScenarioModel.user_id == user_id)
                .order_by(ScenarioModel.created_at.desc())
                .all()
            )
            return [_to_schema(row) for row in rows]

    def get(self, scenario_id: str, *, user_id: str) -> ScenarioResponse | None:
        with self._session_factory() as session:
            row = (
                session.query(ScenarioModel)
                .filter(ScenarioModel.id == scenario_id, ScenarioModel.user_id == user_id)
                .one_or_none()
            )
            return None if row is None else _to_schema(row)


def _to_model(scenario: ScenarioResponse) -> ScenarioModel:
    return ScenarioModel(
        id=scenario.id,
        user_id=scenario.user_id,
        title=scenario.title,
        scenario_type=scenario.scenario_type.value,
        ticker=scenario.ticker,
        sector=scenario.sector,
        shock_percent=scenario.shock_percent,
        rate_bps=scenario.rate_bps,
        currency=scenario.currency,
        assumptions=scenario.assumptions,
        portfolio_impact=scenario.portfolio_impact,
        affected_holdings=[item.model_dump(mode="json") for item in scenario.affected_holdings],
        risk_level=scenario.risk_level,
        recommendation=scenario.recommendation,
        approval_required=scenario.approval_required,
        created_at=scenario.created_at,
    )


def _to_schema(model: ScenarioModel) -> ScenarioResponse:
    return ScenarioResponse(
        id=model.id,
        user_id=model.user_id,
        title=model.title,
        scenario_type=ScenarioType(model.scenario_type),
        ticker=model.ticker,
        sector=model.sector,
        shock_percent=model.shock_percent,
        rate_bps=model.rate_bps,
        currency=model.currency,
        assumptions=list(model.assumptions),
        portfolio_impact=model.portfolio_impact,
        affected_holdings=[ScenarioImpactItem.model_validate(item) for item in model.affected_holdings],
        risk_level=model.risk_level,
        recommendation=model.recommendation,
        approval_required=model.approval_required,
        created_at=model.created_at,
    )
