"""Tests for the FRED / fallback macro-data integration."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from alphalens.core.config import Settings
from alphalens.integrations.macro.base import MacroDataError
from alphalens.integrations.macro.fallback_client import FallbackMacroClient
from alphalens.integrations.macro.fred_client import FredMacroClient
from alphalens.schemas.agent import ChatMessage, ChatRequest, ChatRole
from alphalens.schemas.macro import MacroObservation, MacroSnapshot
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.chat_service import ChatService
from alphalens.services.macro_service import MacroService, get_macro_service
from alphalens.services.market_data_service import get_market_data_service
from alphalens.services.rag_service import RAGService
from alphalens.tools.macro_tool import make_macro_snapshot_tool
from alphalens.tools.market_data_tool import make_market_data_tool
from alphalens.tools.portfolio_tool import make_portfolio_tool
from alphalens.tools.rag_tool import make_rag_tool
from alphalens.tools.registry import ToolRegistry
from alphalens.tools.risk_tool import make_risk_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HOLDINGS_HEADER = (
    "symbol,name,sector,strategy_bucket,quantity,avg_cost,current_price,current_weight\n"
)


def _write_clean_holdings(path: Path) -> Path:
    csv = path / "holdings.csv"
    csv.write_text(
        HOLDINGS_HEADER
        + "AAA,Alpha,Software,Quality Compounders,100,50,50,0\n"
        + "ENE,Energy Co,Energy,Defensive,100,50,50,0\n",
        encoding="utf-8",
    )
    return csv


@pytest.fixture
def kb_dir(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "policy.md").write_text("# Policy\n", encoding="utf-8")
    return kb


def _fred_payload(
    observations: list[dict] | None = None,
) -> dict:
    if observations is None:
        observations = [
            {"date": "2024-11-01", "value": "4.58"},
            {"date": "2024-10-01", "value": "4.83"},
        ]
    return {
        "realtime_start": "2024-12-01",
        "realtime_end": "2024-12-01",
        "observation_start": "1600-01-01",
        "observation_end": "9999-12-31",
        "units": "lin",
        "output_type": 1,
        "file_type": "json",
        "order_by": "observation_date",
        "sort_order": "desc",
        "count": len(observations),
        "offset": 0,
        "limit": len(observations),
        "observations": observations,
    }


# ---------------------------------------------------------------------------
# 1. No API key -> fallback macro client is used
# ---------------------------------------------------------------------------


def test_no_api_key_uses_fallback_macro_client() -> None:
    settings = Settings(macro_data_provider="fred", fred_api_key=None)
    service = get_macro_service(settings)

    snapshot = service.get_macro_snapshot()

    assert snapshot.provider == "fallback"
    series_ids = {o.series_id for o in snapshot.observations}
    assert {"FEDFUNDS", "CPIAUCSL", "UNRATE", "GDP"} == series_ids


def test_provider_fallback_ignores_api_key() -> None:
    settings = Settings(macro_data_provider="fallback", fred_api_key="some-key")
    service = get_macro_service(settings)

    snapshot = service.get_macro_snapshot()

    assert snapshot.provider == "fallback"


# ---------------------------------------------------------------------------
# 2. Fallback snapshot is deterministic
# ---------------------------------------------------------------------------


def test_fallback_snapshot_is_deterministic() -> None:
    client_a = FallbackMacroClient()
    client_b = FallbackMacroClient()

    snap_a = client_a.get_macro_snapshot()
    snap_b = client_b.get_macro_snapshot()

    assert len(snap_a.observations) == len(snap_b.observations)
    for obs_a, obs_b in zip(snap_a.observations, snap_b.observations):
        assert obs_a.series_id == obs_b.series_id
        assert obs_a.value == obs_b.value
        assert obs_a.date == obs_b.date


def test_fallback_snapshot_has_all_default_series() -> None:
    client = FallbackMacroClient()
    snapshot = client.get_macro_snapshot()

    assert isinstance(snapshot, MacroSnapshot)
    series_ids = {o.series_id for o in snapshot.observations}
    assert series_ids == {"FEDFUNDS", "CPIAUCSL", "UNRATE", "GDP"}

    for obs in snapshot.observations:
        assert isinstance(obs, MacroObservation)
        assert obs.provider == "fallback"
        assert obs.value > 0


def test_fallback_get_series_returns_correct_limit() -> None:
    client = FallbackMacroClient()
    resp = client.get_series("FEDFUNDS", limit=3)

    assert resp.series_id == "FEDFUNDS"
    assert len(resp.observations) == 3
    assert resp.provider == "fallback"


def test_fallback_unknown_series_returns_empty() -> None:
    client = FallbackMacroClient()
    resp = client.get_series("UNKNOWN_SERIES")

    assert resp.series_id == "UNKNOWN_SERIES"
    assert resp.observations == []
    assert resp.provider == "fallback"


# ---------------------------------------------------------------------------
# 3. FRED response parses observations correctly (mocked httpx)
# ---------------------------------------------------------------------------


def test_fred_parses_observations_correctly() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fred_payload())

    client = FredMacroClient(
        api_key="test-key",
        timeout=10.0,
    )
    # Inject mock transport
    client._timeout = 10.0
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client._http = http
        # Patch _fetch_observations to use our mock client
        pass

    # Direct test via mocked httpx at module level
    def handler2(request: httpx.Request) -> httpx.Response:
        assert "series_id=FEDFUNDS" in str(request.url)
        assert "api_key=test-key" in str(request.url)
        assert "sort_order=desc" in str(request.url)
        return httpx.Response(200, json=_fred_payload())

    transport = httpx.MockTransport(handler2)

    import alphalens.integrations.macro.fred_client as fred_module

    original_get = httpx.get

    def mock_get(url, *, params=None, timeout=None):
        full_url = httpx.URL(url, params=params)
        req = httpx.Request("GET", full_url)
        return transport.handle_request(req)

    import unittest.mock as mock

    with mock.patch("httpx.get", side_effect=mock_get):
        result = client.get_series("FEDFUNDS", limit=2)

    assert result.series_id == "FEDFUNDS"
    assert result.provider == "fred"
    assert len(result.observations) == 2
    assert result.observations[0].value == pytest.approx(4.58)
    assert result.observations[0].date == date(2024, 11, 1)
    assert result.observations[1].value == pytest.approx(4.83)


# ---------------------------------------------------------------------------
# 4. FRED "." values are skipped
# ---------------------------------------------------------------------------


def test_fred_dot_values_are_skipped() -> None:
    payload = _fred_payload(
        observations=[
            {"date": "2024-11-01", "value": "4.58"},
            {"date": "2024-10-01", "value": "."},  # FRED missing value
            {"date": "2024-09-01", "value": "5.13"},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)

    import unittest.mock as mock

    def mock_get(url, *, params=None, timeout=None):
        full_url = httpx.URL(url, params=params)
        req = httpx.Request("GET", full_url)
        return transport.handle_request(req)

    client = FredMacroClient(api_key="test-key")
    with mock.patch("httpx.get", side_effect=mock_get):
        result = client.get_series("FEDFUNDS", limit=3)

    assert len(result.observations) == 2
    values = [o.value for o in result.observations]
    assert pytest.approx(4.58) in values
    assert pytest.approx(5.13) in values


# ---------------------------------------------------------------------------
# 5. FRED error falls back cleanly at service layer
# ---------------------------------------------------------------------------


def test_fred_error_falls_back_at_service_layer() -> None:
    failing_client = MagicMock()
    failing_client.get_macro_snapshot.side_effect = MacroDataError("FRED is down")

    service = MacroService.__new__(MacroService)
    service._primary = failing_client
    service._fallback = FallbackMacroClient()

    snapshot = service.get_macro_snapshot()

    assert snapshot.provider == "fallback"
    failing_client.get_macro_snapshot.assert_called_once()


def test_fred_series_error_falls_back_at_service_layer() -> None:
    failing_client = MagicMock()
    failing_client.get_series.side_effect = MacroDataError("timeout")

    service = MacroService.__new__(MacroService)
    service._primary = failing_client
    service._fallback = FallbackMacroClient()

    result = service.get_series("FEDFUNDS", limit=3)

    assert result.provider == "fallback"
    assert result.series_id == "FEDFUNDS"


# ---------------------------------------------------------------------------
# 6. macro_snapshot tool returns provider and observations
# ---------------------------------------------------------------------------


def test_macro_snapshot_tool_returns_provider_and_observations() -> None:
    service = MacroService(Settings(macro_data_provider="fallback"))
    tool = make_macro_snapshot_tool(service)

    result = tool()

    assert result.name == "macro_snapshot"
    assert result.data["provider"] == "fallback"
    assert isinstance(result.data["as_of"], str)
    assert len(result.data["observations"]) == 4
    for obs in result.data["observations"]:
        assert "series_id" in obs
        assert "value" in obs
        assert "date" in obs
        assert "provider" in obs


def test_macro_snapshot_tool_with_explicit_series() -> None:
    service = MacroService(Settings(macro_data_provider="fallback"))
    tool = make_macro_snapshot_tool(service)

    result = tool(series_ids=["FEDFUNDS", "UNRATE"])

    assert result.name == "macro_snapshot"
    assert result.data["provider"] == "fallback"
    series_ids = {o["series_id"] for o in result.data["observations"]}
    assert series_ids == {"FEDFUNDS", "UNRATE"}


# ---------------------------------------------------------------------------
# 7. Agent macro query uses macro_snapshot
# ---------------------------------------------------------------------------


def _build_agent_service(
    tmp_path: Path, kb_dir: Path
) -> tuple[ChatService, ApprovalsService]:
    csv = _write_clean_holdings(tmp_path)
    settings = Settings(
        knowledge_base_path=str(kb_dir),
        rag_collection=f"macro_test_{tmp_path.name}",
        macro_data_provider="fallback",
    )
    rag_service = RAGService(settings)
    approvals_service = ApprovalsService()
    registry = ToolRegistry()
    registry.register(make_portfolio_tool(holdings_path=csv))
    registry.register(make_risk_tool(holdings_path=csv))
    registry.register(make_market_data_tool(get_market_data_service(settings)))
    registry.register(make_rag_tool(rag_service))
    registry.register(make_macro_snapshot_tool(MacroService(settings)))
    service = ChatService(
        settings=settings,
        rag_service=rag_service,
        approvals_service=approvals_service,
        registry=registry,
    )
    return service, approvals_service


def test_agent_macro_query_uses_macro_snapshot(
    tmp_path: Path, kb_dir: Path
) -> None:
    service, _ = _build_agent_service(tmp_path, kb_dir)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content="What is the current Fed interest rate and inflation?",
                )
            ]
        )
    )

    assert "macro_snapshot" in response.used_tools
    decision = response.decision
    assert decision is not None
    macro_ev = next(ev for ev in decision.evidence if ev.tool == "macro_snapshot")
    assert macro_ev.data["provider"] == "fallback"
    series_ids = {o["series_id"] for o in macro_ev.data["observations"]}
    assert "FEDFUNDS" in series_ids


# ---------------------------------------------------------------------------
# 8. Trade idea with macro terms uses macro_snapshot plus market_quote
# ---------------------------------------------------------------------------


def test_trade_idea_with_macro_terms_uses_macro_and_market(
    tmp_path: Path, kb_dir: Path
) -> None:
    service, _ = _build_agent_service(tmp_path, kb_dir)

    response = service.chat(
        ChatRequest(
            messages=[
                ChatMessage(
                    role=ChatRole.USER,
                    content=(
                        "Should I buy NVDA given the current GDP growth "
                        "and Fed rates environment?"
                    ),
                )
            ]
        )
    )

    assert "macro_snapshot" in response.used_tools
    assert "market_quote" in response.used_tools
    decision = response.decision
    assert decision is not None
    assert decision.intent in {"trade_idea", "investment_recommendation"}
