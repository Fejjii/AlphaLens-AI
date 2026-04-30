# Risk Playbook

**Version:** 2026.1
**Owner:** Risk Committee
**Last reviewed:** 2026-02-28

## 1. Risk philosophy

Risk is managed by limits, not by forecasts. The playbook defines the
hard thresholds at which automatic responses fire, and the soft
thresholds at which the agent must escalate to a human.

## 2. Portfolio-level thresholds

| Metric | Soft threshold | Hard threshold | Action on hard breach |
| --- | --- | --- | --- |
| Annualized volatility | 22% | 28% | Reduce gross exposure by 20% |
| 30-day drawdown | -8% | -12% | De-risk to defensive bucket; pause new buys |
| 12-month max drawdown | -12% | -15% | Convene emergency committee |
| Beta to ACWI | 1.2 | 1.4 | Hedge with index puts or short ETF |
| Sharpe ratio (TTM) | < 0.8 | < 0.5 | Strategy review |
| VaR 95% / 1-day | 2.0% | 3.0% | Reduce highest-vol positions |

## 3. Position-level thresholds

- **Stop-loss:** any single position drawing down > 25% from average
  cost triggers a mandatory review within one trading day.
- **Concentration:** any single position exceeding 12% of NAV triggers
  a trim recommendation; > 15% triggers a forced trim within five
  trading days.
- **Liquidity:** any single position whose 30-day ADV would require
  more than 10 days to fully liquidate at 20% of ADV is flagged.

## 4. Sector and factor thresholds

- Sector exposure within 5 percentage points of the IPS limit triggers a
  warning. At the limit, no new buys in that sector.
- Factor exposures (momentum, growth, quality) must remain within +/- 1
  standard deviation of strategic targets, measured weekly.

## 5. Macro overlays

When any of the following triggers fire, the agent must include a
macro-risk caveat in any new trade rationale:

- VIX > 25 for 5 consecutive sessions.
- 10y US Treasury yield moves > 50 bps in 10 sessions.
- Major credit spread (HY OAS) widens > 100 bps in 20 sessions.
- USD trade-weighted index moves > 4% in 20 sessions.

## 6. Operational risk

- All trade tickets must be idempotent (signed `trade_id`).
- Approvals expire after 24 hours; expired approvals must not be
  re-executed without re-approval.
- Tool calls that mutate broker state must be wrapped in a two-phase
  confirm: simulate, then commit.

## 7. Escalation

- **Tier 1 (agent-only):** soft thresholds breached.
- **Tier 2 (PM approval):** hard threshold breached on a single metric.
- **Tier 3 (Committee):** two or more hard thresholds simultaneously, or
  any policy breach lasting > 5 trading days.
