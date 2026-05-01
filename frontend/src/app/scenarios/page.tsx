"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/ui/error-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { RiskBadge } from "@/components/ui/status-badges";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent } from "@/lib/utils";
import type { ScenarioCreate, ScenarioResponse, ScenarioSummary, ScenarioType } from "@/types/api";

const SCENARIO_TYPES: Array<{ id: ScenarioType; label: string }> = [
  { id: "price_shock", label: "Price shock" },
  { id: "rate_shock", label: "Rate shock" },
  { id: "sector_shock", label: "Sector shock" },
  { id: "fx_shock", label: "FX shock" },
  { id: "rebalance", label: "Rebalance" },
];

export default function ScenariosPage() {
  const [scenarios, setScenarios] = useState<ScenarioResponse[]>([]);
  const [summary, setSummary] = useState<ScenarioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    scenarioType: "price_shock" as ScenarioType,
    ticker: "",
    sector: "",
    shockPercent: "-0.10",
    rateBps: "100",
    currency: "USD",
    assumptions: "",
  });

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.fetchScenarios(), api.fetchScenarioSummary()])
      .then(([scenariosData, summaryData]) => {
        if (cancelled) return;
        setScenarios(scenariosData);
        setSummary(summaryData);
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load scenarios.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const canSubmit = useMemo(() => {
    if (form.scenarioType === "price_shock") return form.ticker.trim().length > 0;
    if (form.scenarioType === "sector_shock") return form.sector.trim().length > 0;
    if (form.scenarioType === "fx_shock") return form.currency.trim().length > 0;
    return true;
  }, [form]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload: ScenarioCreate = {
        title: form.title.trim() || null,
        scenario_type: form.scenarioType,
        ticker: form.ticker.trim() || null,
        sector: form.sector.trim() || null,
        shock_percent: Number.isFinite(Number(form.shockPercent))
          ? Number(form.shockPercent)
          : null,
        rate_bps: Number.isFinite(Number(form.rateBps)) ? Number(form.rateBps) : null,
        currency: form.currency.trim() || null,
        assumptions: form.assumptions
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      };
      const created = await api.createScenario(payload);
      setScenarios((prev) => [created, ...prev]);
      setSummary((prev) => ({
        total_scenarios: (prev?.total_scenarios ?? 0) + 1,
        by_type: {
          ...(prev?.by_type ?? {}),
          [created.scenario_type]: (prev?.by_type?.[created.scenario_type] ?? 0) + 1,
        },
      }));
    } catch {
      setError("Failed to run scenario simulation.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Scenarios"
        description="Run deterministic what-if simulations for portfolio stress and planning."
      />

      {error && !loading ? (
        <ErrorBanner
          title="Scenario service unavailable"
          message={error}
          actionLabel="Retry"
          onAction={() => window.location.reload()}
          className="mb-4"
        />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Run scenario</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={submit}>
              <Input
                placeholder="Title (optional)"
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
              />
              <select
                value={form.scenarioType}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, scenarioType: event.target.value as ScenarioType }))
                }
                className="h-11 w-full rounded-[0.875rem] border border-border bg-background px-3 text-sm"
              >
                {SCENARIO_TYPES.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>

              {(form.scenarioType === "price_shock" || form.scenarioType === "rebalance") && (
                <Input
                  placeholder="Ticker (optional for rebalance)"
                  value={form.ticker}
                  onChange={(event) => setForm((prev) => ({ ...prev, ticker: event.target.value }))}
                />
              )}
              {form.scenarioType === "sector_shock" && (
                <Input
                  placeholder="Sector"
                  value={form.sector}
                  onChange={(event) => setForm((prev) => ({ ...prev, sector: event.target.value }))}
                />
              )}
              {form.scenarioType === "fx_shock" && (
                <Input
                  placeholder="Currency (e.g. USD)"
                  value={form.currency}
                  onChange={(event) => setForm((prev) => ({ ...prev, currency: event.target.value }))}
                />
              )}
              {(form.scenarioType === "price_shock" ||
                form.scenarioType === "sector_shock" ||
                form.scenarioType === "fx_shock") && (
                <Input
                  placeholder="Shock percent (e.g. -0.10)"
                  value={form.shockPercent}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, shockPercent: event.target.value }))
                  }
                />
              )}
              {form.scenarioType === "rate_shock" && (
                <Input
                  placeholder="Rate move bps (e.g. 100)"
                  value={form.rateBps}
                  onChange={(event) => setForm((prev) => ({ ...prev, rateBps: event.target.value }))}
                />
              )}
              <textarea
                className="min-h-20 w-full rounded-[0.875rem] border border-border bg-background px-3 py-2.5 text-sm"
                placeholder="Optional assumptions (one per line)"
                value={form.assumptions}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, assumptions: event.target.value }))
                }
              />
              <Button type="submit" disabled={!canSubmit || submitting}>
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Simulating
                  </>
                ) : (
                  "Run simulation"
                )}
              </Button>
              {error && <p className="text-sm text-danger">Scenario writes require the live backend endpoint.</p>}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Scenario summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <SummaryStat label="Total scenarios" value={String(summary?.total_scenarios ?? 0)} />
            <div className="rounded-[0.875rem] border border-border/60 bg-background/40 p-3 text-xs text-muted-foreground">
              {Object.entries(summary?.by_type ?? {}).length === 0
                ? "No scenario breakdown yet."
                : Object.entries(summary?.by_type ?? {})
                    .map(([type, count]) => `${type.replaceAll("_", " ")}: ${count}`)
                    .join(" · ")}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mt-6">
        {loading ? (
          <ScenariosSkeleton />
        ) : scenarios.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="No scenarios have been run"
            description="Stress tests and rebalance simulations will appear here with portfolio impact, affected holdings, and whether human approval is required."
            eyebrow="What-if analysis"
          />
        ) : (
          <div className="space-y-3">
            {scenarios.map((scenario) => (
              <Card key={scenario.id}>
                <CardContent className="space-y-4 p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-base font-semibold">{scenario.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {new Date(scenario.created_at).toLocaleString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="muted" className="capitalize">
                        {scenario.scenario_type.replaceAll("_", " ")}
                      </Badge>
                      <RiskBadge level={scenario.risk_level} />
                      <Badge variant={scenario.approval_required ? "warning" : "success"}>
                        {scenario.approval_required ? "Approval required" : "No approval"}
                      </Badge>
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <SummaryStat
                      label="Portfolio impact"
                      value={formatCurrency(scenario.portfolio_impact)}
                    />
                    <SummaryStat
                      label="Affected holdings"
                      value={String(scenario.affected_holdings.length)}
                    />
                    <SummaryStat label="Recommendation" value={scenario.recommendation} />
                  </div>

                  <div className="rounded-[0.875rem] border border-border/60 bg-card/60 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                      Assumptions
                    </div>
                    <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                      {scenario.assumptions.map((item, index) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  {scenario.disclaimer && (
                    <div className="rounded-[0.875rem] border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
                      {scenario.disclaimer}
                    </div>
                  )}
                  {scenario.limitations && scenario.limitations.length > 0 && (
                    <div className="rounded-[0.875rem] border border-border/60 bg-card/60 p-3 text-xs text-muted-foreground">
                      {scenario.limitations.join(" · ")}
                    </div>
                  )}
                  {scenario.approval_required_reason && (
                    <div className="text-xs text-muted-foreground">
                      Approval reason: {scenario.approval_required_reason}
                    </div>
                  )}

                  <div className="rounded-[0.875rem] border border-border/60 bg-card/60 p-3">
                    <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                      Affected holdings
                    </div>
                    <div className="mt-2 space-y-1">
                      {scenario.affected_holdings.map((item) => (
                        <div
                          key={`${scenario.id}_${item.symbol}`}
                          className="flex items-center justify-between text-sm"
                        >
                          <span>{item.symbol}</span>
                          <span className="tabular text-muted-foreground">
                            {formatCurrency(item.delta_usd)} ({formatPercent(item.delta_pct)})
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[0.875rem] border border-border/60 bg-background/40 px-3 py-2.5">
      <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}

function ScenariosSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, index) => (
        <Card key={index}>
          <CardContent className="space-y-4 pt-6">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-2">
                <Skeleton className="h-5 w-44" />
                <Skeleton className="h-4 w-36" />
              </div>
              <Skeleton className="h-8 w-28" />
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
            <Skeleton className="h-24 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
