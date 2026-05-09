"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Loader2 } from "lucide-react";

import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/ui/error-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { ReportResponse, ReportType } from "@/types/api";

const REPORT_TYPES: ReportType[] = ["investment_memo", "risk_review", "portfolio_update"];

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    title: "",
    reportType: "investment_memo" as ReportType,
    ticker: "",
    prompt: "",
  });
  const [expandedReportId, setExpandedReportId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .fetchReports()
      .then((data) => {
        if (!cancelled) setReports(data);
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load reports.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const summary = useMemo(
    () => ({
      total: reports.length,
      memos: reports.filter((report) => report.report_type === "investment_memo").length,
      risk: reports.filter((report) => report.report_type === "risk_review").length,
    }),
    [reports],
  );

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.prompt.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createReport({
        title: form.title.trim() || null,
        report_type: form.reportType,
        ticker: form.ticker.trim() || null,
        prompt: form.prompt.trim(),
      });
      setReports((prev) => [created, ...prev]);
      setExpandedReportId(created.id);
      setForm((prev) => ({ ...prev, title: "", ticker: "", prompt: "" }));
    } catch {
      setError("Failed to generate report.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Reports"
        description="Generate structured investment memos, risk reviews, and portfolio updates."
      />

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>Create report</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={submit}>
              <Input
                placeholder="Title (optional)"
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <select
                  value={form.reportType}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, reportType: event.target.value as ReportType }))
                  }
                  className="h-11 rounded-[0.875rem] border border-border bg-background px-3 text-sm"
                >
                  {REPORT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type.replaceAll("_", " ")}
                    </option>
                  ))}
                </select>
                <Input
                  placeholder="Ticker (optional)"
                  value={form.ticker}
                  onChange={(event) => setForm((prev) => ({ ...prev, ticker: event.target.value }))}
                />
              </div>
              <textarea
                className="min-h-24 w-full rounded-[0.875rem] border border-border bg-background px-3 py-2.5 text-sm"
                placeholder="Question or investigation context"
                value={form.prompt}
                onChange={(event) => setForm((prev) => ({ ...prev, prompt: event.target.value }))}
              />
              <Button type="submit" disabled={submitting || !form.prompt.trim()}>
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating
                  </>
                ) : (
                  "Generate report"
                )}
              </Button>
              {error && <ErrorBanner title="Report generation failed" message={error} />}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Report summary</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 sm:grid-cols-3">
            <SummaryStat label="Total" value={String(summary.total)} />
            <SummaryStat label="Memos" value={String(summary.memos)} />
            <SummaryStat label="Risk reviews" value={String(summary.risk)} />
          </CardContent>
        </Card>
      </div>

      <div className="mt-6">
        {loading ? (
          <ReportsSkeleton />
        ) : reports.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No reports generated yet"
            description="Turn a chat response or a direct investigation brief into a memo, risk review, or portfolio update. Generated reports remain deterministic when fallback mode is active."
            eyebrow="Research outputs"
          />
        ) : (
          <div className="space-y-3">
            {reports.map((report) => {
              const expanded = expandedReportId === report.id;
              return (
                <Card key={report.id}>
                  <CardContent className="space-y-3 p-5">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-base font-semibold">{report.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(report.created_at).toLocaleString()}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="muted" className="capitalize">
                          {report.report_type.replaceAll("_", " ")}
                        </Badge>
                        <Badge variant="success" className="uppercase">
                          {report.status}
                        </Badge>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setExpandedReportId(expanded ? null : report.id)}
                        >
                          {expanded ? "Hide" : "View"}
                        </Button>
                      </div>
                    </div>

                    {expanded && (
                      <div className="space-y-3 rounded-[0.875rem] border border-border/60 bg-card/60 p-3">
                        {report.memo_metadata?.limited_context ? (
                          <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
                            Limited context memo: some market or portfolio fields were unavailable.
                          </div>
                        ) : null}
                        {report.disclaimer && (
                          <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
                            {report.disclaimer}
                          </div>
                        )}
                        <div className="flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                          <Badge variant="outline">Source: {report.source_response_id ? "Agent decision" : "Manual"}</Badge>
                          <Badge variant="outline">
                            Approval: {report.memo_metadata?.approval_id ?? "none"}
                          </Badge>
                          <Badge variant="outline">
                            Evidence: {report.evidence_count ?? report.evidence.length}
                          </Badge>
                          <Badge variant="outline">
                            RAG sources: {report.memo_metadata?.rag_sources_count ?? 0}
                          </Badge>
                        </div>
                        {report.approval_required_reason && (
                          <div className="text-xs text-muted-foreground">
                            Approval reason: {report.approval_required_reason}
                          </div>
                        )}
                        {report.sections.map((section) => (
                          <div key={section.key} className="space-y-1">
                            <h3 className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                              {section.title}
                            </h3>
                            <p className="text-sm">{section.content}</p>
                            {section.bullets.length > 0 && (
                              <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                                {section.bullets.map((bullet, idx) => (
                                  <li key={idx}>{bullet}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))}
                        <div className="text-xs text-muted-foreground">
                          Evidence items: {report.evidence_count ?? report.evidence.length}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
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
      <div className="mt-1 text-lg font-semibold">{value}</div>
    </div>
  );
}

function ReportsSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }).map((_, index) => (
        <Card key={index}>
          <CardContent className="space-y-3 pt-6">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-2">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-4 w-36" />
              </div>
              <Skeleton className="h-9 w-20" />
            </div>
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
