from __future__ import annotations

from httpx import AsyncClient

from alphalens.api import deps
from alphalens.schemas.scenario import ScenarioCreate
from alphalens.services.scenarios_service import ScenariosService, _resolve_holdings_path
from alphalens.tools.portfolio_tool import load_holdings


def test_runtime_holdings_path_resolves_to_existing_csv() -> None:
    path = _resolve_holdings_path()
    assert path.exists()
    assert path.name == "portfolio_holdings.csv"
    assert load_holdings(path)


def test_price_shock_scenario_is_deterministic() -> None:
    service = ScenariosService()
    scenario = service.create_scenario(
        ScenarioCreate(
            scenario_type="price_shock",
            ticker="NVDA",
            shock_percent=-0.1,
            assumptions=["Use deterministic synthetic valuation snapshot."],
        ),
        user_id="usr_scenario_test",
    )
    assert scenario.scenario_type == "price_shock"
    assert scenario.ticker == "NVDA"
    assert scenario.affected_holdings
    assert scenario.affected_holdings[0].symbol == "NVDA"
    assert scenario.affected_holdings[0].delta_pct == -0.1


async def test_scenarios_api_roundtrip(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    create_response = await client.post(
        "/scenarios",
        json={
            "scenario_type": "sector_shock",
            "sector": "Semiconductors",
            "shock_percent": -0.12,
        },
        headers=auth_headers,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["id"].startswith("scn_")
    assert created["scenario_type"] == "sector_shock"
    assert created["affected_holdings"]

    list_response = await client.get("/scenarios", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    summary_response = await client.get("/scenarios/summary", headers=auth_headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["total_scenarios"] == 1
    assert summary["by_type"]["sector_shock"] == 1

    get_response = await client.get(f"/scenarios/{created['id']}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


async def test_scenario_generation_records_usage_event(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    deps.get_usage_service().reset()
    response = await client.post(
        "/scenarios",
        json={"scenario_type": "rate_shock", "rate_bps": 100},
        headers=auth_headers,
    )
    assert response.status_code == 200
    events = deps.get_usage_service().list_usage_events()
    assert any(event.event_type == "scenario_simulated" for event in events)
