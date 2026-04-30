"""Portfolio-related schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from alphalens.schemas.common import APIModel, Money


class Position(APIModel):
    symbol: str = Field(..., examples=["AAPL"])
    quantity: Decimal
    average_cost: Money
    market_value: Money
    unrealized_pnl: Money
    weight: float = Field(..., ge=0, le=1, description="Share of NAV in [0, 1].")


class RiskMetric(APIModel):
    name: str = Field(..., examples=["sharpe", "max_drawdown", "beta"])
    value: float
    unit: str | None = None


class PortfolioSummary(APIModel):
    portfolio_id: str
    as_of: str = Field(..., description="ISO 8601 timestamp.")
    nav: Money
    day_pnl: Money
    day_pnl_pct: float
    positions: list[Position]
    risk_metrics: list[RiskMetric]
