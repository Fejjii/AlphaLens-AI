import { Inbox } from "lucide-react";

import { AlertCard } from "@/components/cards/AlertCard";
import { PendingApprovalsPanel } from "@/components/dashboard/PendingApprovalsPanel";
import { MetricCard } from "@/components/cards/MetricCard";
import { UsageMetricCard } from "@/components/cards/UsageMetricCard";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { serverApi } from "@/lib/api.server";
import { formatCurrency, formatPercent } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [portfolio, approvals, usageSummary] = await Promise.all([
    serverApi.portfolioSummary(),
    serverApi.approvals("pending"),
    serverApi.fetchUsageSummary(),
  ]);

  const sharpe = portfolio.risk_metrics.find((m) => m.name === "sharpe");
  const drawdown = portfolio.risk_metrics.find((m) => m.name === "max_drawdown");

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Live portfolio snapshot, alerts, and pending approvals."
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Net Asset Value"
          value={formatCurrency(portfolio.nav.amount, portfolio.nav.currency)}
          hint={`as of ${new Date(portfolio.as_of).toLocaleString()}`}
        />
        <MetricCard
          label="Day P&L"
          value={formatCurrency(portfolio.day_pnl.amount, portfolio.day_pnl.currency)}
          delta={{
            value: formatPercent(portfolio.day_pnl_pct),
            direction: portfolio.day_pnl_pct >= 0 ? "up" : "down",
          }}
        />
        <MetricCard
          label="Sharpe (TTM)"
          value={sharpe ? sharpe.value.toFixed(2) : "—"}
        />
        <MetricCard
          label="Max Drawdown"
          value={drawdown ? formatPercent(drawdown.value) : "—"}
          delta={{
            value: "trailing 12m",
            direction: "flat",
          }}
        />
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-3">
        <UsageMetricCard
          label="Usage Cost (Est.)"
          value={`$${usageSummary.estimated_cost_usd.toFixed(4)}`}
          hint="View full usage analytics"
          href="/usage"
        />
        <UsageMetricCard
          label="Total Tokens"
          value={usageSummary.total_tokens.toLocaleString("en-US")}
          hint="Accumulated runtime tokens"
          href="/usage"
        />
        <UsageMetricCard
          label="Tool Calls"
          value={usageSummary.tool_calls.toLocaleString("en-US")}
          hint="Tracked tool invocations"
          href="/usage"
        />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle>Top positions</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {portfolio.positions.length === 0 ? (
                <div className="p-6">
                  <EmptyState
                    icon={Inbox}
                    title="No positions available"
                    description="Portfolio holdings will appear here once a live or fallback snapshot is loaded."
                    eyebrow="Portfolio snapshot"
                  />
                </div>
              ) : (
                <table className="table-base">
                  <thead>
                    <tr className="table-head-row">
                      <th className="table-head-cell">Symbol</th>
                      <th className="table-head-cell">Quantity</th>
                      <th className="table-head-cell">Market value</th>
                      <th className="table-head-cell">Unrealized P&L</th>
                      <th className="table-head-cell">Weight</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolio.positions.map((p) => (
                      <tr key={p.symbol} className="table-row">
                        <td className="table-cell font-medium">{p.symbol}</td>
                        <td className="table-cell tabular text-muted-foreground">{p.quantity}</td>
                        <td className="table-cell tabular">
                          {formatCurrency(p.market_value.amount, p.market_value.currency)}
                        </td>
                        <td className="table-cell tabular text-success">
                          {formatCurrency(p.unrealized_pnl.amount, p.unrealized_pnl.currency)}
                        </td>
                        <td className="table-cell tabular text-muted-foreground">
                          {formatPercent(p.weight)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          <div className="space-y-3">
            <h2 className="text-sm font-medium text-muted-foreground">Alerts</h2>
            <AlertCard
              severity="warning"
              title="Concentration risk: MSFT exceeds 35%"
              description="Single-name exposure above policy limit. Consider trimming or hedging."
              source="agent.risk"
              timestamp="just now"
            />
            <AlertCard
              severity="info"
              title="New research note ready for review"
              description="'Semiconductors H2 Outlook' (6 pages, 12 citations)."
              source="agent.research"
              timestamp="10m ago"
            />
          </div>
        </div>

        <PendingApprovalsPanel initialApprovals={approvals} />
      </div>
    </div>
  );
}
