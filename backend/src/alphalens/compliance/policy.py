"""Financial compliance and recommendation safety policy."""

from __future__ import annotations

from dataclasses import dataclass, field

DISCLAIMER_TEXT = (
    "AlphaLens provides decision support and educational analysis only. "
    "It is not investment, legal, tax, or trading advice."
)

LIMITATIONS_TEXT = "Outputs are deterministic summaries of available context and may omit market data."

SENSITIVE_ACTIONS = {"buy", "sell", "trim", "rebalance", "escalate"}


@dataclass(frozen=True, slots=True)
class ComplianceAssessment:
    approval_required: bool
    approval_required_reason: str | None = None
    policy_flags: list[str] = field(default_factory=list)
    recommendation_override: str | None = None


def assess_compliance(
    *,
    recommendation: str,
    risk_level: str,
    confidence: float,
    evidence_count: int,
    ticker_supported: bool = True,
    portfolio_impact: float | None = None,
) -> ComplianceAssessment:
    flags: list[str] = []
    approval_required = recommendation in SENSITIVE_ACTIONS or risk_level in {"high", "critical"}

    if confidence < 0.55:
        flags.append("low_confidence")
        approval_required = True
    if evidence_count == 0:
        flags.append("missing_evidence")
        approval_required = True
    if not ticker_supported:
        flags.append("unsupported_ticker")
        approval_required = True
    if portfolio_impact is not None and abs(portfolio_impact) >= 30000:
        flags.append("large_portfolio_impact")
        approval_required = True
    if risk_level in {"high", "critical"}:
        flags.append("high_risk_level")

    recommendation_override = None
    if evidence_count == 0 or confidence < 0.55:
        recommendation_override = "needs_more_analysis"

    reason = None
    if flags:
        reason = ", ".join(flags)

    return ComplianceAssessment(
        approval_required=approval_required,
        approval_required_reason=reason,
        policy_flags=flags,
        recommendation_override=recommendation_override,
    )
