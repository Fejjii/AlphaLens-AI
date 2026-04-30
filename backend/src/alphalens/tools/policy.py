"""Numeric policy thresholds extracted from the Investment Policy Statement.

The markdown at `data/knowledge_base/investment_policy.md` is the
human-readable source of truth. These constants mirror the numeric
limits so tools can enforce them deterministically without parsing prose.

Keep this module in sync with the IPS. The IPS section is referenced in
each docstring so reviewers can cross-check.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Limits:
    """Hard limits from IPS v2026.1."""

    single_name_max_weight: float = 0.15
    """IPS section 5.1: single position cap at market value."""

    single_name_trim_threshold: float = 0.12
    """Risk Playbook section 3: trim recommendation threshold."""

    sector_max_weight: dict[str, float] = None  # type: ignore[assignment]
    """IPS section 5.2: per-sector caps. None entries default to 0.20."""

    cash_min_weight: float = 0.02
    cash_max_weight: float = 0.15
    """IPS section 6: liquidity policy."""


_DEFAULT_SECTOR_LIMITS: dict[str, float] = {
    "Semiconductors": 0.35,
    "Software": 0.35,
    "Energy": 0.15,
    "Financials": 0.20,
}

DEFAULT_SECTOR_FALLBACK = 0.20
"""IPS section 5.2: any sector not explicitly listed."""

POLICY = Limits(sector_max_weight=_DEFAULT_SECTOR_LIMITS)
POLICY_DOC = "investment_policy.md"
