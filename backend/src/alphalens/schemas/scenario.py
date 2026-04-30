"""Scenario simulation schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import Field

from alphalens.schemas.common import APIModel


class ScenarioType(str, Enum):
    PRICE_SHOCK = "price_shock"
    RATE_SHOCK = "rate_shock"
    SECTOR_SHOCK = "sector_shock"
    FX_SHOCK = "fx_shock"
    REBALANCE = "rebalance"


class ScenarioImpactItem(APIModel):
    symbol: str
    sector: str | None = None
    current_value_usd: float
    shocked_value_usd: float
    delta_usd: float
    delta_pct: float


class ScenarioCreate(APIModel):
    title: str | None = None
    scenario_type: ScenarioType
    ticker: str | None = None
    sector: str | None = None
    shock_percent: float | None = Field(default=None, ge=-1.0, le=1.0)
    rate_bps: int | None = None
    currency: str | None = None
    assumptions: list[str] = Field(default_factory=list)


class ScenarioResponse(APIModel):
    id: str
    title: str
    scenario_type: ScenarioType
    ticker: str | None = None
    sector: str | None = None
    shock_percent: float | None = None
    rate_bps: int | None = None
    currency: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    portfolio_impact: float
    affected_holdings: list[ScenarioImpactItem] = Field(default_factory=list)
    risk_level: str
    recommendation: str
    approval_required: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class ScenarioSummary(APIModel):
    total_scenarios: int
    by_type: dict[str, int] = Field(default_factory=dict)
