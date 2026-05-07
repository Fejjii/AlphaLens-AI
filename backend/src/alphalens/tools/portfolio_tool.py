"""Portfolio analysis tool.

Loads holdings from `portfolio_holdings.csv`, computes total value,
sector exposure, position weights, and a concentration metric, and
returns a structured payload the agent can forward as evidence.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

from alphalens.tools.registry import Tool, ToolResult


@dataclass(frozen=True, slots=True)
class Holding:
    symbol: str
    name: str
    sector: str
    strategy_bucket: str
    quantity: float
    avg_cost: float
    current_price: float

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price


@dataclass(frozen=True, slots=True)
class PositionStat:
    symbol: str
    sector: str
    strategy_bucket: str
    market_value: float
    weight: float
    return_estimate: float


@dataclass(frozen=True, slots=True)
class PortfolioAnalysis:
    total_value: float
    position_count: int
    sector_exposure: dict[str, float]
    bucket_exposure: dict[str, float]
    positions: list[PositionStat]
    top_position: PositionStat | None
    hhi: float
    """Herfindahl-Hirschman index over weights, in [0, 1]. Higher = more concentrated."""


def load_holdings(path: Path) -> list[Holding]:
    if not path.exists():
        raise FileNotFoundError(f"Holdings file not found: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [_row_to_holding(row) for row in reader]


def _row_to_holding(row: dict[str, str]) -> Holding:
    return Holding(
        symbol=row["symbol"].strip(),
        name=row["name"].strip(),
        sector=row["sector"].strip(),
        strategy_bucket=row["strategy_bucket"].strip(),
        quantity=float(row["quantity"]),
        avg_cost=float(row["avg_cost"]),
        current_price=float(row["current_price"]),
    )


def analyze_portfolio(*, holdings_path: Path) -> PortfolioAnalysis:
    """Compute portfolio aggregates from a holdings CSV.

    Weights are computed off the equity sleeve only (cash excluded).
    """

    holdings = load_holdings(holdings_path)
    if not holdings:
        return PortfolioAnalysis(
            total_value=0.0,
            position_count=0,
            sector_exposure={},
            bucket_exposure={},
            positions=[],
            top_position=None,
            hhi=0.0,
        )

    total_value = sum(h.market_value for h in holdings)
    sector_exposure: dict[str, float] = {}
    bucket_exposure: dict[str, float] = {}
    positions: list[PositionStat] = []

    for h in holdings:
        weight = h.market_value / total_value if total_value > 0 else 0.0
        positions.append(
            PositionStat(
                symbol=h.symbol,
                sector=h.sector,
                strategy_bucket=h.strategy_bucket,
                market_value=h.market_value,
                weight=weight,
                return_estimate=(h.current_price - h.avg_cost) / h.avg_cost
                if h.avg_cost
                else 0.0,
            )
        )
        sector_exposure[h.sector] = sector_exposure.get(h.sector, 0.0) + weight
        bucket_exposure[h.strategy_bucket] = (
            bucket_exposure.get(h.strategy_bucket, 0.0) + weight
        )

    positions.sort(key=lambda p: p.weight, reverse=True)
    hhi = sum(p.weight * p.weight for p in positions)

    return PortfolioAnalysis(
        total_value=total_value,
        position_count=len(positions),
        sector_exposure=sector_exposure,
        bucket_exposure=bucket_exposure,
        positions=positions,
        top_position=positions[0] if positions else None,
        hhi=hhi,
    )


def make_portfolio_tool(*, holdings_path: Path) -> Tool:
    """Factory: return a Tool bound to a holdings CSV path."""

    def _run() -> ToolResult:
        analysis = analyze_portfolio(holdings_path=holdings_path)
        top = analysis.top_position
        summary = (
            f"Portfolio total ${analysis.total_value:,.0f} across "
            f"{analysis.position_count} positions; "
            f"top: {top.symbol} at {top.weight:.1%}"
            if top
            else "Portfolio is empty."
        )
        return ToolResult(name="portfolio_analyze", summary=summary, data=_to_dict(analysis))

    return Tool(
        name="portfolio_analyze",
        description="Compute total value, sector / bucket exposure, position weights, and concentration.",
        func=_run,
    )


def _to_dict(analysis: PortfolioAnalysis) -> dict:
    weighted_return = sum(p.weight * p.return_estimate for p in analysis.positions)
    top_contributors = sorted(
        analysis.positions,
        key=lambda p: p.return_estimate,
        reverse=True,
    )[:3]
    laggards = sorted(
        analysis.positions,
        key=lambda p: p.return_estimate,
    )[:3]
    return {
        "total_value": analysis.total_value,
        "position_count": analysis.position_count,
        "sector_exposure": analysis.sector_exposure,
        "bucket_exposure": analysis.bucket_exposure,
        "positions": [asdict(p) for p in analysis.positions],
        "top_position": asdict(analysis.top_position) if analysis.top_position else None,
        "hhi": analysis.hhi,
        "estimated_one_month_return": weighted_return,
        "estimated_day_pnl": analysis.total_value * (weighted_return / 21 if weighted_return else 0.0),
        "top_contributors": [
            {"symbol": p.symbol, "return": p.return_estimate}
            for p in top_contributors
        ],
        "laggards": [
            {"symbol": p.symbol, "return": p.return_estimate}
            for p in laggards
        ],
    }
