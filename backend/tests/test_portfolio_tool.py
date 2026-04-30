from __future__ import annotations

from pathlib import Path

import pytest

from alphalens.tools.portfolio_tool import (
    analyze_portfolio,
    load_holdings,
    make_portfolio_tool,
)


@pytest.fixture
def holdings_csv(tmp_path: Path) -> Path:
    path = tmp_path / "holdings.csv"
    path.write_text(
        "symbol,name,sector,strategy_bucket,quantity,avg_cost,current_price,current_weight\n"
        "AAA,Alpha,Software,Quality Compounders,100,10,20,0.4\n"
        "BBB,Beta,Software,Quality Compounders,50,20,40,0.4\n"
        "CCC,Gamma,Energy,Defensive,10,50,100,0.2\n",
        encoding="utf-8",
    )
    return path


def test_load_holdings_parses_rows(holdings_csv: Path) -> None:
    holdings = load_holdings(holdings_csv)
    assert [h.symbol for h in holdings] == ["AAA", "BBB", "CCC"]
    assert holdings[0].market_value == pytest.approx(2000.0)


def test_load_holdings_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_holdings(tmp_path / "nope.csv")


def test_analyze_portfolio_aggregates(holdings_csv: Path) -> None:
    analysis = analyze_portfolio(holdings_path=holdings_csv)
    assert analysis.position_count == 3
    assert analysis.total_value == pytest.approx(5000.0)
    assert analysis.sector_exposure["Software"] == pytest.approx(0.8)
    assert analysis.sector_exposure["Energy"] == pytest.approx(0.2)
    assert analysis.bucket_exposure["Quality Compounders"] == pytest.approx(0.8)
    assert analysis.top_position is not None
    assert analysis.top_position.symbol in {"AAA", "BBB"}
    assert 0.0 < analysis.hhi <= 1.0


def test_portfolio_tool_returns_summary_and_data(holdings_csv: Path) -> None:
    tool = make_portfolio_tool(holdings_path=holdings_csv)
    result = tool()
    assert result.name == "portfolio_analyze"
    assert "Portfolio total" in result.summary
    assert result.data["total_value"] == pytest.approx(5000.0)
    assert "positions" in result.data
