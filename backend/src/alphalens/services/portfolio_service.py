"""Portfolio service.

Returns deterministic mock data so the rest of the stack (API, FE, tests)
can develop against a stable contract before real persistence and market
data are wired in.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from alphalens.schemas.common import Money
from alphalens.schemas.portfolio import PortfolioSummary, Position, RiskMetric


def _money(amount: str, currency: str = "USD") -> Money:
    return Money(amount=Decimal(amount), currency=currency)


class PortfolioService:
    """Read-side use cases for portfolios."""

    def get_summary(self, portfolio_id: str = "demo") -> PortfolioSummary:
        positions = [
            Position(
                symbol="AAPL",
                quantity=Decimal("1200"),
                average_cost=_money("145.20"),
                market_value=_money("228000.00"),
                unrealized_pnl=_money("53760.00"),
                weight=0.34,
            ),
            Position(
                symbol="MSFT",
                quantity=Decimal("600"),
                average_cost=_money("298.50"),
                market_value=_money("252000.00"),
                unrealized_pnl=_money("72900.00"),
                weight=0.38,
            ),
            Position(
                symbol="NVDA",
                quantity=Decimal("250"),
                average_cost=_money("420.00"),
                market_value=_money("187500.00"),
                unrealized_pnl=_money("82500.00"),
                weight=0.28,
            ),
        ]

        risk_metrics = [
            RiskMetric(name="sharpe", value=1.42),
            RiskMetric(name="max_drawdown", value=-0.087, unit="ratio"),
            RiskMetric(name="beta", value=1.08),
            RiskMetric(name="volatility_annualized", value=0.214, unit="ratio"),
        ]

        return PortfolioSummary(
            portfolio_id=portfolio_id,
            as_of=datetime.now(tz=UTC).isoformat(),
            nav=_money("667500.00"),
            day_pnl=_money("4820.50"),
            day_pnl_pct=0.0072,
            positions=positions,
            risk_metrics=risk_metrics,
        )
