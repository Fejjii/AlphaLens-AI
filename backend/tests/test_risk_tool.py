from __future__ import annotations

from pathlib import Path

import pytest

from alphalens.tools.portfolio_tool import analyze_portfolio
from alphalens.tools.risk_tool import Severity, evaluate_risk, make_risk_tool


def _write_holdings(path: Path, rows: list[tuple[str, str, str, float, float]]) -> Path:
    """rows = [(symbol, sector, bucket, quantity, price)]."""

    csv = path / "holdings.csv"
    header = "symbol,name,sector,strategy_bucket,quantity,avg_cost,current_price,current_weight\n"
    body = "\n".join(
        f"{sym},{sym} Corp,{sector},{bucket},{qty},{price},{price},0"
        for sym, sector, bucket, qty, price in rows
    )
    csv.write_text(header + body + "\n", encoding="utf-8")
    return csv


def test_clean_portfolio_has_no_findings(tmp_path: Path) -> None:
    csv = _write_holdings(
        tmp_path,
        [
            ("AAA", "Software", "Quality Compounders", 100, 50),
            ("AAB", "Software", "Quality Compounders", 100, 50),
            ("AAC", "Software", "Quality Compounders", 100, 50),
            ("ENE", "Energy", "Defensive", 100, 50),
            ("FIN", "Financials", "Defensive", 100, 50),
            ("IND", "Industrials", "Defensive", 100, 50),
            ("HLT", "Healthcare", "Defensive", 100, 50),
            ("UTL", "Utilities", "Defensive", 100, 50),
            ("CST", "Consumer Staples", "Defensive", 100, 50),
            ("MAT", "Materials", "Defensive", 100, 50),
            ("REA", "Real Estate", "Defensive", 100, 50),
        ],
    )
    analysis = analyze_portfolio(holdings_path=csv)
    report = evaluate_risk(analysis)
    assert report.status == "clean"
    assert report.findings == []


def test_single_name_violation_detected(tmp_path: Path) -> None:
    csv = _write_holdings(
        tmp_path,
        [
            ("BIG", "Software", "Quality Compounders", 100, 100),
            ("SML", "Energy", "Defensive", 1, 100),
        ],
    )
    analysis = analyze_portfolio(holdings_path=csv)
    report = evaluate_risk(analysis)
    assert report.status == "violations"
    codes = {f.code for f in report.findings}
    assert "single_name_max" in codes


def test_single_name_warning_at_trim_threshold(tmp_path: Path) -> None:
    # 13% AAA position triggers the trim warning (>=12%, <15%).
    csv = _write_holdings(
        tmp_path,
        [
            ("AAA", "Software", "Quality Compounders", 13, 100),
            ("BBB", "Energy", "Defensive", 87, 100),
        ],
    )
    analysis = analyze_portfolio(holdings_path=csv)
    report = evaluate_risk(analysis)
    aaa_findings = [f for f in report.findings if f.subject == "AAA"]
    assert any(
        f.code == "single_name_trim" and f.severity is Severity.WARNING
        for f in aaa_findings
    )


def test_sector_violation_detected(tmp_path: Path) -> None:
    # Energy capped at 15%; build an 80% energy book.
    csv = _write_holdings(
        tmp_path,
        [
            ("E1", "Energy", "Defensive", 40, 100),
            ("E2", "Energy", "Defensive", 40, 100),
            ("S1", "Software", "Quality Compounders", 20, 100),
        ],
    )
    analysis = analyze_portfolio(holdings_path=csv)
    report = evaluate_risk(analysis)
    energy_findings = [f for f in report.findings if f.subject == "Energy"]
    assert any(f.code == "sector_max" for f in energy_findings)
    assert report.status == "violations"


def test_risk_tool_summary_reports_counts(tmp_path: Path) -> None:
    csv = _write_holdings(
        tmp_path,
        [
            ("BIG", "Software", "Quality Compounders", 100, 100),
            ("SML", "Energy", "Defensive", 1, 100),
        ],
    )
    tool = make_risk_tool(holdings_path=csv)
    result = tool()
    assert result.name == "risk_check"
    assert "violation" in result.summary.lower()
    assert result.data["status"] == "violations"


def test_findings_carry_policy_reference(tmp_path: Path) -> None:
    csv = _write_holdings(
        tmp_path, [("BIG", "Software", "Quality Compounders", 100, 100)]
    )
    analysis = analyze_portfolio(holdings_path=csv)
    report = evaluate_risk(analysis)
    assert report.findings, "expected at least one finding"
    assert all(f.policy_ref.endswith(".md") for f in report.findings)
