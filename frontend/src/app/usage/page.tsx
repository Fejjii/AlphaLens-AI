"use client";

import type { ComponentType } from "react";
import { useEffect, useMemo, useState } from "react";
import { Clock3, Monitor, Sparkles, Wrench } from "lucide-react";

import { UsageMetricCard } from "@/components/cards/UsageMetricCard";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { UsageEventsTable } from "@/components/tables/UsageEventsTable";
import { Badge } from "@/components/ui/badge";
import { ErrorBanner } from "@/components/ui/error-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { FeedbackSummary, PlanUsage, UsageEvent, UsageSummary } from "@/types/api";

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

function formatTokens(value: number): string {
  return value.toLocaleString("en-US");
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function getEventLabel(eventType: UsageEvent["event_type"]): string {
  switch (eventType) {
    case "llm_call":
      return "LLM call";
    case "llm_fallback":
      return "LLM fallback";
    case "llm_error":
      return "LLM error";
    case "tool_call":
      return "Tool call";
    case "tool_error":
      return "Tool error";
    case "cache_hit":
      return "Cache hit";
    default:
      return eventType.replaceAll("_", " ");
  }
}

export default function UsagePage() {
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [events, setEvents] = useState<UsageEvent[]>([]);
  const [feedbackSummary, setFeedbackSummary] = useState<FeedbackSummary | null>(null);
  const [planUsage, setPlanUsage] = useState<PlanUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      api.fetchUsageSummary(),
      api.fetchUsageEvents(),
      api.fetchFeedbackSummary(),
      api.fetchMyPlanUsage(),
    ])
      .then(([summaryData, eventsData, feedbackData, planUsageData]) => {
        if (cancelled) return;
        setSummary(summaryData);
        setEvents(eventsData);
        setFeedbackSummary(feedbackData);
        setPlanUsage(planUsageData);
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load usage data right now.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const recentEvents = useMemo(
    () =>
      [...events]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 25),
    [events],
  );

  const analytics = useMemo(() => {
    const byProvider = new Map<string, number>();
    const byTool = new Map<string, number>();
    const byType = new Map<UsageEvent["event_type"], number>();
    let fallbackEvents = 0;
    let cacheHitEvents = 0;

    for (const event of events) {
      byProvider.set(event.provider, (byProvider.get(event.provider) ?? 0) + 1);
      byType.set(event.event_type, (byType.get(event.event_type) ?? 0) + 1);
      if (event.tool_name) {
        byTool.set(event.tool_name, (byTool.get(event.tool_name) ?? 0) + 1);
      }
      if (event.event_type === "llm_fallback") fallbackEvents += 1;
      if (event.event_type === "cache_hit") cacheHitEvents += 1;
    }

    return {
      byProvider: [...byProvider.entries()].sort((a, b) => b[1] - a[1]),
      byTool: [...byTool.entries()].sort((a, b) => b[1] - a[1]),
      byType: [...byType.entries()].sort((a, b) => b[1] - a[1]),
      fallbackEvents,
      cacheHitEvents,
    };
  }, [events]);

  return (
    <div>
      <PageHeader
        title="Usage"
        description="Track token usage, estimated cost, runtime events, and tool reliability in one place."
      />

      {loading ? (
        <UsageSkeleton />
      ) : error ? (
        <>
          <ErrorBanner
            title="Usage analytics unavailable"
            message={error}
            actionLabel="Retry"
            onAction={() => window.location.reload()}
            className="mb-4"
          />
          <EmptyState
            icon={Clock3}
            title="Usage analytics are temporarily unavailable"
            description="Retry to restore the telemetry stream. Fallback data does not synthesize live event history, so this page prefers clarity over invented activity."
          />
        </>
      ) : !summary ? (
        <EmptyState
          icon={Clock3}
          title="No usage summary available"
          description="Usage tracking may not be initialized yet."
        />
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <UsageMetricCard
              label="Estimated Cost"
              value={formatCost(summary.estimated_cost_usd)}
              hint="USD estimate"
            />
            <UsageMetricCard
              label="Total Events"
              value={formatTokens(summary.total_events)}
              hint="LLM, tool, cache, and fallback events"
            />
            <UsageMetricCard
              label="LLM Events"
              value={formatTokens(summary.llm_calls)}
              hint={`${formatPercent(summary.llm_calls / Math.max(summary.total_events, 1))} of events`}
            />
            <UsageMetricCard
              label="Tool Events"
              value={formatTokens(summary.tool_calls)}
              hint={`${formatPercent(summary.tool_calls / Math.max(summary.total_events, 1))} of events`}
            />
            <UsageMetricCard
              label="Fallback Events"
              value={formatTokens(analytics.fallbackEvents)}
              hint="Retries or provider fallbacks"
            />
            <UsageMetricCard
              label="Cache Hit Events"
              value={formatTokens(analytics.cacheHitEvents)}
              hint="Visible when the runtime emits cache telemetry"
            />
            <UsageMetricCard
              label="Feedback Items"
              value={formatTokens(feedbackSummary?.total_feedback ?? 0)}
              hint="Response ratings captured from chat"
            />
          </div>
          {planUsage && (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Monthly quota usage</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {Object.entries(planUsage.monthly_usage).map(([key, value]) => (
                    <div
                      key={key}
                      className="flex items-center justify-between rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2.5 text-sm"
                    >
                      <span className="capitalize text-muted-foreground">{key.replaceAll("_", " ")}</span>
                      <span className="tabular">{String(value)}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Plan features</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="text-sm text-muted-foreground">
                    Enabled tools and models for your current plan.
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {planUsage.capabilities.tools.map((tool) => (
                      <Badge key={tool} variant="muted">
                        {tool}
                      </Badge>
                    ))}
                    {planUsage.capabilities.models.map((modelName) => (
                      <Badge key={modelName} variant="outline">
                        {modelName}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.4fr_0.9fr]">
            <Card>
              <CardHeader>
                <CardTitle>Recent Usage Events</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {recentEvents.length === 0 ? (
                  <EmptyState
                    icon={Clock3}
                    title="No usage events yet"
                    description="Run a few chat turns and tool calls to populate this table."
                  />
                ) : (
                  <UsageEventsTable events={recentEvents} />
                )}
              </CardContent>
            </Card>

            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Feedback summary</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-md border border-border/60 px-3 py-2">
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Thumbs up</div>
                    <div className="mt-1 text-lg font-semibold">{feedbackSummary?.thumbs_up ?? 0}</div>
                  </div>
                  <div className="rounded-md border border-border/60 px-3 py-2">
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Thumbs down</div>
                    <div className="mt-1 text-lg font-semibold">{feedbackSummary?.thumbs_down ?? 0}</div>
                  </div>
                  <div className="rounded-md border border-border/60 px-3 py-2">
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Categories</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {Object.entries(feedbackSummary?.by_category ?? {})
                        .map(([key, value]) => `${key}: ${value}`)
                        .join(" · ") || "No categories yet"}
                    </div>
                  </div>
                </CardContent>
              </Card>
              <BreakdownCard
                title="Most used tools"
                icon={Wrench}
                items={analytics.byTool}
                emptyLabel="Tool usage will appear once tool telemetry is emitted."
              />
              <BreakdownCard
                title="Providers by volume"
                icon={Monitor}
                items={analytics.byProvider}
                emptyLabel="Provider activity is still waiting on runtime data."
              />
              <BreakdownCard
                title="Event mix"
                icon={Sparkles}
                items={analytics.byType.map(([type, count]) => [getEventLabel(type), count])}
                emptyLabel="Event type breakdown will appear after a few agent runs."
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

interface BreakdownCardProps {
  title: string;
  icon: ComponentType<{ className?: string }>;
  items: Array<[string, number]>;
  emptyLabel: string;
}

function BreakdownCard({ title, icon: Icon, items, emptyLabel }: BreakdownCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="h-4 w-4" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyLabel}</p>
        ) : (
          items.slice(0, 5).map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-3 rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2.5">
              <span className="text-sm font-medium">{label}</span>
              <Badge variant="muted" className="tabular">
                {value}
              </Badge>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function UsageSkeleton() {
  return (
    <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Card key={index}>
            <CardContent className="space-y-3 pt-6">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-9 w-32" />
              <Skeleton className="h-4 w-44" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-[1.4fr_0.9fr]">
        <Card>
          <CardContent className="space-y-3 pt-6">
            <Skeleton className="h-5 w-40" />
            {Array.from({ length: 5 }).map((_, index) => (
              <Skeleton key={index} className="h-12 w-full" />
            ))}
          </CardContent>
        </Card>
        <div className="space-y-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Card key={index}>
              <CardContent className="space-y-3 pt-6">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </>
  );
}
