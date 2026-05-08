"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Inbox } from "lucide-react";

import { ApprovalCard } from "@/components/cards/ApprovalCard";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorBanner } from "@/components/ui/error-banner";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { Approval, ApprovalDecisionStatus } from "@/types/api";

type FlashKind = "success" | "error";

interface Flash {
  kind: FlashKind;
  message: string;
}

const DECISION_LABEL: Record<ApprovalDecisionStatus, string> = {
  approved: "approved",
  rejected: "rejected",
  needs_more_analysis: "sent for more analysis",
  cancelled: "cancelled",
};

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<Flash | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listApprovals()
      .then((items) => {
        if (!cancelled) setApprovals(items);
      })
      .catch(() => {
        if (!cancelled) setError("Unable to load approvals.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-dismiss flash after a short delay so the page returns to a calm state.
  useEffect(() => {
    if (!flash) return;
    const timer = setTimeout(() => setFlash(null), 3500);
    return () => clearTimeout(timer);
  }, [flash]);

  const handleDecide = useCallback(
    async (approvalId: string, status: ApprovalDecisionStatus) => {
      try {
        if (status === "approved") {
          await api.approveApproval(approvalId);
        } else if (status === "rejected") {
          await api.rejectApproval(approvalId);
        } else if (status === "needs_more_analysis") {
          await api.requestMoreAnalysis(approvalId);
        } else {
          await api.decideApproval(approvalId, { status });
        }
        const refreshed = await api.listApprovals();
        setApprovals(refreshed);
        setFlash({
          kind: "success",
          message: `Approval ${approvalId} ${DECISION_LABEL[status]}.`,
        });
      } catch {
        setFlash({
          kind: "error",
          message: `Failed to record decision for ${approvalId}.`,
        });
      }
    },
    [],
  );

  const pendingCount = useMemo(
    () => approvals.filter((a) => a.status === "pending").length,
    [approvals],
  );

  return (
    <div>
      <PageHeader
        title="Approvals"
        description={
          loading
            ? "Loading approval queue..."
            : `${pendingCount} pending approval${pendingCount === 1 ? "" : "s"} awaiting human sign-off.`
        }
      />

      {flash && (
        <div
          className={`mb-4 flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
            flash.kind === "success"
              ? "border-success/30 bg-success/10 text-success"
              : "border-danger/30 bg-danger/10 text-danger"
          }`}
          role="status"
        >
          <CheckCircle2 className="h-4 w-4" />
          {flash.message}
        </div>
      )}

      {loading ? (
        <ApprovalsSkeleton />
      ) : error ? (
        <>
          <ErrorBanner
            title="Approvals queue unavailable"
            message={error}
            actionLabel="Retry"
            onAction={() => window.location.reload()}
            className="mb-4"
          />
          <EmptyState
            icon={Inbox}
            title="Approval queue unavailable"
            description="Retry to reconnect to the runtime. Deterministic fallbacks keep the rest of the product demoable, but approval decisions still need the live endpoint."
          />
        </>
      ) : approvals.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No approvals are waiting"
          description="When AlphaLens escalates a trade, rebalance, or memo for review, it will land here with rationale, evidence, and a clear audit trail."
          eyebrow="Human review queue"
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {approvals.map((a) => (
            <ApprovalCard key={a.approval_id} approval={a} onDecide={handleDecide} />
          ))}
        </div>
      )}
    </div>
  );
}

function ApprovalsSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <Card key={index}>
          <CardContent className="space-y-4">
            <Skeleton className="h-4 w-24" />
            <div className="space-y-2">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-56" />
            </div>
            <Skeleton className="h-24 w-full" />
            <div className="grid gap-2 sm:grid-cols-3">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
            <div className="grid gap-2 sm:grid-cols-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
