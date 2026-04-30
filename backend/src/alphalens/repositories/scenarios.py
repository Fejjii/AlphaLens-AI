"""Scenario repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from alphalens.schemas.scenario import ScenarioResponse


class ScenarioRepository(Protocol):
    def create(self, scenario: ScenarioResponse) -> ScenarioResponse: ...

    def list(self) -> list[ScenarioResponse]: ...

    def get(self, scenario_id: str) -> ScenarioResponse | None: ...


@dataclass(slots=True)
class InMemoryScenarioRepository(ScenarioRepository):
    _records: dict[str, ScenarioResponse] = field(default_factory=dict)

    def create(self, scenario: ScenarioResponse) -> ScenarioResponse:
        self._records[scenario.id] = scenario
        return scenario

    def list(self) -> list[ScenarioResponse]:
        return sorted(self._records.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, scenario_id: str) -> ScenarioResponse | None:
        return self._records.get(scenario_id)

    def clear(self) -> None:
        self._records.clear()
