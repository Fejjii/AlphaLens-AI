"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import type { Investigation } from "@/types/api";

const START_PROMPT =
  "Use RAG and internal policy documents to explain whether NVDA should be trimmed.";

const EMPTY_PROMPTS = [
  "Use RAG and internal policy documents to explain whether NVDA should be trimmed.",
  "Which policy rules are currently breached by the portfolio?",
  "Why is NVDA moving today?",
];

function formatDate(value: string): string {
  const t = Date.parse(value);
  if (Number.isNaN(t)) return value;
  return new Date(t).toLocaleString();
}

export default function InvestigationsPage() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void api
      .fetchInvestigations()
      .then((items) => {
        if (!cancelled) {
          setInvestigations(items);
          setExpandedId(items[0]?.id ?? null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load investigations.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => investigations.find((item) => item.id === expandedId) ?? null,
    [expandedId, investigations],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title="Investigations"
        description="Persistent audit timeline for multi-step agent investment workflows."
      />
      {loading ? (
        <Card>
          <CardContent className="p-4 text-sm text-muted-foreground">Loading investigations...</CardContent>
        </Card>
      ) : null}
      {error ? (
        <Card>
          <CardContent className="p-4 text-sm text-destructive">{error}</CardContent>
        </Card>
      ) : null}
      {!loading && !error && investigations.length === 0 ? (
        <Card>
          <CardContent className="space-y-4 p-6">
            <div className="text-lg font-semibold">No investigations yet</div>
            <p className="text-sm text-muted-foreground">
              Ask the agent an investment question that requires tools or evidence, such as:
            </p>
            <ul className="space-y-2 text-sm text-muted-foreground">
              {EMPTY_PROMPTS.map((prompt) => (
                <li key={prompt}>- {prompt}</li>
              ))}
            </ul>
            <Button asChild variant="outline">
              <Link href={`/agent?mode=investigation&prompt=${encodeURIComponent(START_PROMPT)}`}>
                Start from agent chat
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}
      {investigations.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <div className="space-y-3">
            {investigations.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setExpandedId(item.id)}
                className="w-full rounded-xl border border-border/70 bg-card/70 p-4 text-left"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-semibold">{item.title}</div>
                  <Badge variant="outline">{item.status}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>Intent: {item.intent}</span>
                  <span>Subject: {item.subject ?? "n/a"}</span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
                <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{item.summary}</p>
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <Badge variant="muted">Recommendation: {item.recommendation}</Badge>
                  <Badge variant="muted">Risk: {item.risk_level ?? "n/a"}</Badge>
                  <Badge variant="muted">
                    Confidence: {item.confidence != null ? `${Math.round(item.confidence * 100)}%` : "n/a"}
                  </Badge>
                  <Badge variant="muted">Evidence: {item.evidence_items.length}</Badge>
                  <Badge variant="muted">RAG: {item.rag_sources.length}</Badge>
                </div>
              </button>
            ))}
          </div>
          {selected ? (
            <Card>
              <CardContent className="space-y-4 p-4">
                <div className="text-base font-semibold">{selected.title}</div>
                <div className="text-sm text-muted-foreground">{selected.summary}</div>
                <div className="space-y-2 text-sm">
                  <div className="font-medium">Timeline steps</div>
                  <ol className="space-y-1 text-muted-foreground">
                    <li>1. Intent detected: {selected.intent}</li>
                    <li>2. Tools selected: {selected.tools_used.join(", ") || "none"}</li>
                    <li>3. Evidence gathered: {selected.evidence_items.length}</li>
                    <li>4. RAG retrieved: {selected.rag_sources.length}</li>
                    <li>5. Synthesis</li>
                    <li>6. Decision: {selected.recommendation}</li>
                    <li>7. Approval gate: {selected.approval_id ? "linked" : "not required"}</li>
                  </ol>
                </div>
                <details className="rounded-lg border border-border/60 bg-background/50 p-3 text-xs">
                  <summary className="cursor-pointer font-medium">Technical trace</summary>
                  <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap">
                    {JSON.stringify(selected.orchestration_trace, null, 2)}
                  </pre>
                </details>
                <div className="flex flex-wrap gap-2">
                  {selected.tools_used.map((tool) => (
                    <Badge key={tool} variant="outline">
                      {tool}
                    </Badge>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  {selected.approval_id ? <Link href="/approvals">Linked approval</Link> : null}
                  {selected.report_id ? <Link href="/reports">Linked memo</Link> : null}
                  <Link href={`/agent?conversation_id=${encodeURIComponent(selected.conversation_id)}`}>
                    Open conversation
                  </Link>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
