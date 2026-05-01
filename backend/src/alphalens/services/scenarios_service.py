"""Deterministic what-if scenario simulation service."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from alphalens.repositories.scenarios import InMemoryScenarioRepository, ScenarioRepository
from alphalens.compliance.policy import DISCLAIMER_TEXT, LIMITATIONS_TEXT, assess_compliance
from alphalens.schemas.scenario import (
    ScenarioCreate,
    ScenarioImpactItem,
    ScenarioResponse,
    ScenarioSummary,
    ScenarioType,
)
from alphalens.services.usage_service import UsageService
from alphalens.tools.portfolio_tool import Holding, load_holdings

HOLDINGS_RELATIVE_PATH = Path("data/synthetic/portfolio_holdings.csv")
DEFAULT_PRICE_SHOCK = -0.1
DEFAULT_SECTOR_SHOCK = -0.08
DEFAULT_RATE_BPS = 100
DEFAULT_FX_SHOCK = 0.05


class ScenariosService:
    def __init__(
        self,
        repository: ScenarioRepository | None = None,
        usage_service: UsageService | None = None,
    ) -> None:
        self._repository = repository or InMemoryScenarioRepository()
        self._usage_service = usage_service

    def create_scenario(self, payload: ScenarioCreate, *, user_id: str) -> ScenarioResponse:
        holdings = load_holdings(_resolve_holdings_path())
        if not holdings:
            raise ValueError("No synthetic holdings available for scenario simulation.")

        if payload.scenario_type == ScenarioType.PRICE_SHOCK:
            result = _run_price_shock(payload, holdings, user_id=user_id)
        elif payload.scenario_type == ScenarioType.SECTOR_SHOCK:
            result = _run_sector_shock(payload, holdings, user_id=user_id)
        elif payload.scenario_type == ScenarioType.RATE_SHOCK:
            result = _run_rate_shock(payload, holdings, user_id=user_id)
        elif payload.scenario_type == ScenarioType.FX_SHOCK:
            result = _run_fx_shock(payload, holdings, user_id=user_id)
        else:
            result = _run_rebalance(payload, holdings, user_id=user_id)

        created = self._repository.create(result)
        if self._usage_service is not None:
            self._usage_service.record_event(
                event_type="scenario_simulated",
                provider="scenario_service",
                user_id=user_id,
                metadata={
                    "scenario_id": created.id,
                    "scenario_type": created.scenario_type.value,
                    "approval_required": created.approval_required,
                },
            )
        return created

    def list_scenarios(self, *, user_id: str) -> list[ScenarioResponse]:
        return self._repository.list(user_id=user_id)

    def get_scenario(self, scenario_id: str, *, user_id: str) -> ScenarioResponse | None:
        return self._repository.get(scenario_id, user_id=user_id)

    def summarize_scenarios(self, *, user_id: str) -> ScenarioSummary:
        scenarios = self._repository.list(user_id=user_id)
        counts = Counter(item.scenario_type.value for item in scenarios)
        return ScenarioSummary(
            total_scenarios=len(scenarios),
            by_type=dict(sorted(counts.items())),
        )

    def reset(self) -> None:
        clear = getattr(self._repository, "clear", None)
        if callable(clear):
            clear()


def _run_price_shock(
    payload: ScenarioCreate,
    holdings: list[Holding],
    *,
    user_id: str,
) -> ScenarioResponse:
    ticker = (payload.ticker or "").strip().upper()
    shock = payload.shock_percent if payload.shock_percent is not None else DEFAULT_PRICE_SHOCK
    impacted = [
        _impact_item(holding, shock)
        for holding in holdings
        if ticker and holding.symbol.upper() == ticker
    ]
    if not impacted and holdings:
        impacted = [_impact_item(holdings[0], shock)]
    return _build_response(
        payload=payload,
        title=payload.title or f"Price shock · {ticker or 'single position'}",
        user_id=user_id,
        affected_holdings=impacted,
        assumptions=_merge_assumptions(
            payload.assumptions,
            [f"Applied {shock:.1%} price move to selected ticker exposure."],
        ),
    )


def _run_sector_shock(
    payload: ScenarioCreate,
    holdings: list[Holding],
    *,
    user_id: str,
) -> ScenarioResponse:
    sector = (payload.sector or "").strip().lower()
    shock = payload.shock_percent if payload.shock_percent is not None else DEFAULT_SECTOR_SHOCK
    matching = [holding for holding in holdings if sector and sector in holding.sector.lower()]
    if not matching and holdings:
        matching = holdings[:3]
    impacted = [_impact_item(holding, shock) for holding in matching]
    return _build_response(
        payload=payload,
        title=payload.title or f"Sector shock · {payload.sector or 'AI-linked basket'}",
        user_id=user_id,
        affected_holdings=impacted,
        assumptions=_merge_assumptions(
            payload.assumptions,
            [
                f"Applied {shock:.1%} move to matched sector holdings.",
                "Sector matching uses metadata first, then deterministic fallback basket.",
            ],
        ),
    )


def _run_rate_shock(
    payload: ScenarioCreate,
    holdings: list[Holding],
    *,
    user_id: str,
) -> ScenarioResponse:
    rate_bps = payload.rate_bps if payload.rate_bps is not None else DEFAULT_RATE_BPS
    total_value = sum(item.market_value for item in holdings)
    duration_proxy = 0.035  # deterministic sensitivity proxy
    impact_pct = -(rate_bps / 10000) * duration_proxy
    shocked_total = total_value * (1 + impact_pct)
    portfolio_item = ScenarioImpactItem(
        symbol="PORTFOLIO",
        sector=None,
        current_value_usd=round(total_value, 2),
        shocked_value_usd=round(shocked_total, 2),
        delta_usd=round(shocked_total - total_value, 2),
        delta_pct=round(impact_pct, 6),
    )
    return _build_response(
        payload=payload,
        title=payload.title or f"Rate shock · {rate_bps} bps",
        user_id=user_id,
        affected_holdings=[portfolio_item],
        assumptions=_merge_assumptions(
            payload.assumptions,
            [
                "Portfolio duration proxy is deterministic and not instrument-level.",
                f"Rate shift modeled as parallel move of {rate_bps} bps.",
            ],
        ),
    )


def _run_fx_shock(
    payload: ScenarioCreate,
    holdings: list[Holding],
    *,
    user_id: str,
) -> ScenarioResponse:
    currency = (payload.currency or "USD").upper()
    shock = payload.shock_percent if payload.shock_percent is not None else DEFAULT_FX_SHOCK
    total_value = sum(item.market_value for item in holdings)
    exposure_ratio = 0.22  # deterministic proxy
    impacted_value = total_value * exposure_ratio
    delta = -(impacted_value * shock)
    portfolio_item = ScenarioImpactItem(
        symbol=f"{currency} exposure",
        sector=None,
        current_value_usd=round(impacted_value, 2),
        shocked_value_usd=round(impacted_value + delta, 2),
        delta_usd=round(delta, 2),
        delta_pct=round(delta / impacted_value if impacted_value else 0.0, 6),
    )
    return _build_response(
        payload=payload,
        title=payload.title or f"FX shock · {currency}",
        user_id=user_id,
        affected_holdings=[portfolio_item],
        assumptions=_merge_assumptions(
            payload.assumptions,
            [
                f"{currency} strength modeled as {shock:.1%} move.",
                "FX exposure uses deterministic portfolio-level proxy.",
            ],
        ),
    )


def _run_rebalance(
    payload: ScenarioCreate,
    holdings: list[Holding],
    *,
    user_id: str,
) -> ScenarioResponse:
    total_value = sum(item.market_value for item in holdings)
    current_weights = {
        holding.symbol: holding.market_value / total_value for holding in holdings
    }
    target_weight = 1 / len(holdings)
    top_three = sorted(holdings, key=lambda item: item.market_value, reverse=True)[:3]
    impacted: list[ScenarioImpactItem] = []
    for holding in top_three:
        current_value = holding.market_value
        target_value = total_value * target_weight
        impacted.append(
            ScenarioImpactItem(
                symbol=holding.symbol,
                sector=holding.sector,
                current_value_usd=round(current_value, 2),
                shocked_value_usd=round(target_value, 2),
                delta_usd=round(target_value - current_value, 2),
                delta_pct=round(
                    (target_value - current_value) / current_value if current_value else 0.0,
                    6,
                ),
            )
        )
    return _build_response(
        payload=payload,
        title=payload.title or "Rebalance impact summary",
        user_id=user_id,
        affected_holdings=impacted,
        assumptions=_merge_assumptions(
            payload.assumptions,
            [
                "Target rebalance assumes equal-weight normalization across holdings.",
                f"Current top holding weight: {max(current_weights.values()):.1%}",
            ],
        ),
    )


def _impact_item(holding: Holding, shock: float) -> ScenarioImpactItem:
    current = holding.market_value
    shocked = current * (1 + shock)
    return ScenarioImpactItem(
        symbol=holding.symbol,
        sector=holding.sector,
        current_value_usd=round(current, 2),
        shocked_value_usd=round(shocked, 2),
        delta_usd=round(shocked - current, 2),
        delta_pct=round(shock, 6),
    )


def _build_response(
    *,
    payload: ScenarioCreate,
    title: str,
    user_id: str,
    affected_holdings: list[ScenarioImpactItem],
    assumptions: list[str],
) -> ScenarioResponse:
    portfolio_delta = sum(item.delta_usd for item in affected_holdings)
    risk_level = _risk_level(portfolio_delta)
    recommendation = (
        "Escalate to human review before any allocation change."
        if risk_level in {"high", "critical"}
        else "Use as a planning scenario; no execution implied."
    )
    return ScenarioResponse(
        id=f"scn_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        title=title,
        scenario_type=payload.scenario_type,
        ticker=payload.ticker.upper() if payload.ticker else None,
        sector=payload.sector,
        shock_percent=payload.shock_percent,
        rate_bps=payload.rate_bps,
        currency=payload.currency.upper() if payload.currency else None,
        assumptions=assumptions,
        portfolio_impact=round(portfolio_delta, 2),
        affected_holdings=affected_holdings,
        risk_level=risk_level,
        recommendation=recommendation,
        approval_required=(risk_level in {"high", "critical"}) or payload.scenario_type in {ScenarioType.REBALANCE},
        disclaimer=DISCLAIMER_TEXT,
        limitations=[LIMITATIONS_TEXT, "Scenario outputs are not forecasts or guarantees."],
        evidence_count=len(assumptions),
        policy_flags=[],
        approval_required_reason="high_risk_level" if risk_level in {"high", "critical"} else None,
        created_at=datetime.now(tz=UTC),
    )


def _risk_level(portfolio_delta: float) -> str:
    magnitude = abs(portfolio_delta)
    if magnitude >= 75000:
        return "critical"
    if magnitude >= 30000:
        return "high"
    if magnitude >= 10000:
        return "medium"
    return "low"


def _merge_assumptions(custom: list[str], defaults: list[str]) -> list[str]:
    merged = [item.strip() for item in custom if item.strip()]
    for item in defaults:
        if item not in merged:
            merged.append(item)
    return merged


def _resolve_holdings_path() -> Path:
    if HOLDINGS_RELATIVE_PATH.is_absolute() and HOLDINGS_RELATIVE_PATH.exists():
        return HOLDINGS_RELATIVE_PATH
    cwd_candidate = Path.cwd() / HOLDINGS_RELATIVE_PATH
    if cwd_candidate.exists():
        return cwd_candidate
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / HOLDINGS_RELATIVE_PATH
        if candidate.exists():
            return candidate
    return cwd_candidate
