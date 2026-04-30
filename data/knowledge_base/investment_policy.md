# Investment Policy Statement

**Version:** 2026.1
**Owner:** Investment Committee
**Last reviewed:** 2026-03-15

## 1. Purpose and scope

This document codifies the rules under which the AlphaLens portfolio is
managed. It applies to all discretionary equity strategies and binds both
human portfolio managers and the AlphaLens agent. Any deviation requires
explicit written approval from the Investment Committee.

## 2. Investment objectives

- **Primary:** long-term capital appreciation, target 10-12% annualized
  net return over rolling 5-year periods.
- **Secondary:** drawdown control, target maximum drawdown < 15% in any
  rolling 12-month period.
- **Benchmark:** MSCI ACWI for performance attribution.

## 3. Eligible universe

- Listed equities on US, EU, UK, and developed Asia exchanges.
- Minimum daily ADV of $20M USD.
- Minimum market cap of $5B USD at time of purchase.
- ETFs are permitted only as cash-equivalent or hedging instruments.

## 4. Strategy buckets

The portfolio is segmented into three strategy buckets. Each holding
must be tagged with exactly one bucket.

| Bucket | Target weight | Min | Max |
| --- | --- | --- | --- |
| AI Infrastructure | 40% | 30% | 50% |
| Quality Compounders | 35% | 25% | 45% |
| Defensive | 20% | 15% | 30% |
| Cash & equivalents | 5% | 2% | 15% |

## 5. Exposure limits

### 5.1 Single-name limits
- No single position may exceed **10% of NAV** at cost.
- No single position may exceed **15% of NAV** at market value before
  rebalancing is required.

### 5.2 Sector limits
- Semiconductors: max 35% of NAV.
- Software: max 35% of NAV.
- Energy: max 15% of NAV.
- Financials: max 20% of NAV.
- Any single sector other than the above: max 20% of NAV.

### 5.3 Geographic limits
- Non-US developed markets: max 30% of NAV.
- Emerging markets: max 10% of NAV.

## 6. Liquidity policy

- Cash must remain between 2% and 15% of NAV.
- Cash above 10% for more than 20 trading days requires a redeployment
  plan submitted to the committee.
- The portfolio must be able to liquidate 50% of NAV within 5 trading
  days under normal market conditions.

## 7. Approvals

The following actions require human-in-the-loop approval, regardless of
agent confidence:

- Any single trade with notional > $250,000.
- Any change that would breach a sector or single-name limit, even
  temporarily.
- Initiation of a new strategy bucket.
- Publication of external research memos.

## 8. Review cadence

- Daily: positions, P&L, risk dashboard.
- Weekly: drift vs. target weights, watchlist review.
- Monthly: investment committee meeting; minutes archived in
  `portfolio_committee_notes.md`.
- Annually: full IPS review and update.
