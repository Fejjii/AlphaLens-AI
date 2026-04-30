from __future__ import annotations

from httpx import AsyncClient

from alphalens.api import deps
from alphalens.schemas.scenario import ScenarioCreate
from alphalens.services.scenarios_service import ScenariosService


def test_price_shock_scenario_is_deterministic() -> None:
    service = ScenariosService()
    scenario = service.create_scenario(
        ScenarioCreate(
            scenario_type="price_shock",
            ticker="NVDA",
            shock_percent=-0.1,
            assumptions=["Use deterministic synthetic valuation snapshot."],
        )
    )
    assert scenario.scenario_type == "price_shock"
    assert scenario.ticker == "NVDA"
    assert scenario.affected_holdings
    assert scenario.affected_holdings[0].symbol == "NVDA"
    assert scenario.affected_holdings[0].delta_pct == -0.1


async def test_scenarios_api_roundtrip(client: AsyncClient) -> None:
    create_response = await client.post(
        "/scenarios",
        json={
            "scenario_type": "sector_shock",
            "sector": "Semiconductors",
            "shock_percent": -0.12,
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["id"].startswith("scn_")
    assert created["scenario_type"] == "sector_shock"
    assert created["affected_holdings"]

    list_response = await client.get("/scenarios")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    summary_response = await client.get("/scenarios/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total_scenarios"] == 1
    assert summary["by_type"]["sector_shock"] == 1

    get_response = await client.get(f"/scenarios/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


async def test_scenario_generation_records_usage_event(client: AsyncClient) -> None:
    deps.get_usage_service().reset()
    response = await client.post(
        "/scenarios",
        json={"scenario_type": "rate_shock", "rate_bps": 100},
    )
    assert response.status_code == 200
    events = deps.get_usage_service().list_usage_events()
    assert any(event.event_type == "scenario_simulated" for event in events)
