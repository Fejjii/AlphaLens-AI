import { BarChart3 } from "lucide-react";

import { MetricCard } from "@/components/cards/MetricCard";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function PortfolioPage() {
  const portfolio = await api.portfolioSummary();
  const cash = "0.00";
  const topWeight = Math.max(...portfolio.positions.map((position) => position.weight), 0);
  const watchlist = ["QQQ", "XLK", "JPM", "XOM"];

  return (
    <div>
      <PageHeader
        title="Portfolio"
        description={`Portfolio ${portfolio.portfolio_id} · as of ${new Date(portfolio.as_of).toLocaleString()}`}
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="NAV"
          value={formatCurrency(portfolio.nav.amount, portfolio.nav.currency)}
        />
        <MetricCard
          label="Day P&L"
          value={formatCurrency(portfolio.day_pnl.amount, portfolio.day_pnl.currency)}
          delta={{
            value: formatPercent(portfolio.day_pnl_pct),
            direction: portfolio.day_pnl_pct >= 0 ? "up" : "down",
          }}
        />
        <MetricCard label="Positions" value={String(portfolio.positions.length)} />
        <MetricCard label="Cash" value={formatCurrency(cash, portfolio.nav.currency)} hint="Uninvested capital" />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Allocation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {portfolio.positions.length === 0 ? (
              <EmptyState
                icon={BarChart3}
                title="No holdings loaded"
                description="Portfolio allocation appears once holdings are available from the backend or fallback snapshot."
                eyebrow="Allocation"
              />
            ) : (
              portfolio.positions.map((position) => (
                <div key={position.symbol} className="space-y-1.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{position.symbol}</span>
                    <span className="tabular text-muted-foreground">{formatPercent(position.weight)}</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div
                      className="h-2 rounded-full bg-primary/80"
                      style={{ width: `${Math.max(position.weight * 100, 4)}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Risk indicators</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2.5">
              <span className="text-sm text-muted-foreground">Largest allocation</span>
              <Badge variant={topWeight > 0.35 ? "warning" : "success"} className="tabular">
                {formatPercent(topWeight)}
              </Badge>
            </div>
            {portfolio.risk_metrics.map((metric) => (
              <div key={metric.name} className="flex items-center justify-between rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2.5">
                <span className="text-sm text-muted-foreground">{metric.name.replaceAll("_", " ")}</span>
                <span className="tabular text-sm font-medium">
                  {metric.unit === "ratio" ? formatPercent(metric.value) : metric.value.toFixed(2)}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Watchlist</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {watchlist.map((symbol) => (
              <Badge key={symbol} variant="muted" className="px-3 py-1">
                {symbol}
              </Badge>
            ))}
            <div className="w-full rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2.5 text-sm text-muted-foreground">
              Keep an eye on names with better entry quality or lower concentration pressure.
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6 overflow-hidden">
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          <table className="table-base min-w-[860px]">
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
              {portfolio.positions.map((position) => (
                <tr key={position.symbol} className="table-row">
                  <td className="table-cell font-medium">{position.symbol}</td>
                  <td className="table-cell tabular text-muted-foreground">{position.quantity}</td>
                  <td className="table-cell tabular">
                    {formatCurrency(position.market_value.amount, position.market_value.currency)}
                  </td>
                  <td className="table-cell tabular text-success">
                    {formatCurrency(position.unrealized_pnl.amount, position.unrealized_pnl.currency)}
                  </td>
                  <td className="table-cell tabular text-muted-foreground">
                    {formatPercent(position.weight)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
