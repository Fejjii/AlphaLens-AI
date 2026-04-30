"""Risk checks against IPS limits.

Operates on the structured output of `analyze_portfolio` rather than
re-reading the CSV, so the agent can compose tools without redundant
I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from alphalens.tools.policy import (
    DEFAULT_SECTOR_FALLBACK,
    POLICY,
    POLICY_DOC,
)
from alphalens.tools.portfolio_tool import (
    PortfolioAnalysis,
    analyze_portfolio,
)
from alphalens.tools.registry import Tool, ToolResult


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    VIOLATION = "violation"


@dataclass(frozen=True, slots=True)
class RiskFinding:
    severity: Severity
    code: str
    message: str
    subject: str
    observed: float
    limit: float
    policy_ref: str = POLICY_DOC


@dataclass(frozen=True, slots=True)
class RiskReport:
    findings: list[RiskFinding]
    status: Literal["clean", "warnings", "violations"]


def _sector_limit(sector: str) -> float:
    sectors = POLICY.sector_max_weight or {}
    return sectors.get(sector, DEFAULT_SECTOR_FALLBACK)


def evaluate_risk(analysis: PortfolioAnalysis) -> RiskReport:
    """Apply IPS sector and single-name limits to a portfolio analysis."""

    findings: list[RiskFinding] = []

    for pos in analysis.positions:
        if pos.weight >= POLICY.single_name_max_weight:
            findings.append(
                RiskFinding(
                    severity=Severity.VIOLATION,
                    code="single_name_max",
                    message=(
                        f"{pos.symbol} weight {pos.weight:.2%} exceeds single-name "
                        f"cap {POLICY.single_name_max_weight:.0%}"
                    ),
                    subject=pos.symbol,
                    observed=pos.weight,
                    limit=POLICY.single_name_max_weight,
                )
            )
        elif pos.weight >= POLICY.single_name_trim_threshold:
            findings.append(
                RiskFinding(
                    severity=Severity.WARNING,
                    code="single_name_trim",
                    message=(
                        f"{pos.symbol} weight {pos.weight:.2%} above trim threshold "
                        f"{POLICY.single_name_trim_threshold:.0%}"
                    ),
                    subject=pos.symbol,
                    observed=pos.weight,
                    limit=POLICY.single_name_trim_threshold,
                )
            )

    for sector, weight in analysis.sector_exposure.items():
        limit = _sector_limit(sector)
        if weight > limit:
            findings.append(
                RiskFinding(
                    severity=Severity.VIOLATION,
                    code="sector_max",
                    message=(
                        f"Sector {sector} weight {weight:.2%} exceeds cap {limit:.0%}"
                    ),
                    subject=sector,
                    observed=weight,
                    limit=limit,
                )
            )
        elif weight >= limit - 0.05:
            findings.append(
                RiskFinding(
                    severity=Severity.WARNING,
                    code="sector_near_max",
                    message=(
                        f"Sector {sector} weight {weight:.2%} within 5pp of cap {limit:.0%}"
                    ),
                    subject=sector,
                    observed=weight,
                    limit=limit,
                )
            )

    status: Literal["clean", "warnings", "violations"]
    if any(f.severity is Severity.VIOLATION for f in findings):
        status = "violations"
    elif any(f.severity is Severity.WARNING for f in findings):
        status = "warnings"
    else:
        status = "clean"

    return RiskReport(findings=findings, status=status)


def make_risk_tool(*, holdings_path: Path) -> Tool:
    """Factory: a Tool that runs portfolio analysis then risk checks."""

    def _run() -> ToolResult:
        analysis = analyze_portfolio(holdings_path=holdings_path)
        report = evaluate_risk(analysis)
        violations = sum(1 for f in report.findings if f.severity is Severity.VIOLATION)
        warnings = sum(1 for f in report.findings if f.severity is Severity.WARNING)
        summary = (
            f"Risk status: {report.status} "
            f"({violations} violation(s), {warnings} warning(s))"
        )
        return ToolResult(
            name="risk_check",
            summary=summary,
            data={
                "status": report.status,
                "findings": [
                    {
                        "severity": f.severity.value,
                        "code": f.code,
                        "message": f.message,
                        "subject": f.subject,
                        "observed": f.observed,
                        "limit": f.limit,
                        "policy_ref": f.policy_ref,
                    }
                    for f in report.findings
                ],
            },
        )

    return Tool(
        name="risk_check",
        description="Check portfolio against IPS sector and single-name limits.",
        func=_run,
    )
