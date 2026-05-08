"use client";

import { useCallback, useMemo, useState } from "react";
import { CheckCircle2, ClipboardCheck } from "lucide-react";

import { ApprovalCard } from "@/components/cards/ApprovalCard";
import { EmptyState } from "@/components/layout/EmptyState";
import { api, ApiError } from "@/lib/api";
import type { Approval, ApprovalDecisionStatus } from "@/types/api";

interface PendingApprovalsPanelProps {
  initialApprovals: Approval[];
}

const DECISION_LABEL: Record<ApprovalDecisionStatus, string> = {
  approved: "Approved",
  rejected: "Rejected",
  needs_more_analysis: "Marked for more analysis",
  cancelled: "Cancelled",
};

export function PendingApprovalsPanel({ initialApprovals }: PendingApprovalsPanelProps) {
  const [approvals, setApprovals] = useState<Approval[]>(initialApprovals);
  const [flash, setFlash] = useState<string | null>(null);
  const [errorById, setErrorById] = useState<Record<string, string>>({});

  const visibleApprovals = useMemo(() => approvals.slice(0, 3), [approvals]);

  const refreshPendingApprovals = useCallback(async () => {
    const refreshed = await api.listApprovals("pending");
    setApprovals(refreshed);
  }, []);

  const handleDecide = useCallback(
    async (approvalId: string, status: ApprovalDecisionStatus) => {
      setErrorById((prev) => {
        const next = { ...prev };
        delete next[approvalId];
        return next;
      });
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

        await refreshPendingApprovals();
        setFlash(`${DECISION_LABEL[status]}: ${approvalId}`);

        if (process.env.NODE_ENV === "development") {
          // eslint-disable-next-line no-console
          console.debug("[dashboard-approvals] decision applied", {
            approval_id: approvalId,
            action: status,
            updated_status: status,
          });
        }
      } catch (error) {
        const reason =
          error instanceof ApiError
            ? String(error.detail ?? error.message)
            : error instanceof Error
              ? error.message
              : "Unknown error";
        setErrorById((prev) => ({
          ...prev,
          [approvalId]: `Could not update approval. Reason: ${reason}`,
        }));
        if (process.env.NODE_ENV === "development") {
          // eslint-disable-next-line no-console
          console.error("[dashboard-approvals] decision failed", {
            approval_id: approvalId,
            action: status,
            error_detail: reason,
          });
        }
      }
    },
    [refreshPendingApprovals],
  );

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium text-muted-foreground">Pending approvals</h2>
      {flash ? (
        <div className="flex items-center gap-2 rounded-md border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
          <CheckCircle2 className="h-4 w-4" />
          {flash}
        </div>
      ) : null}
      {visibleApprovals.length === 0 ? (
        <EmptyState
          icon={ClipboardCheck}
          title="No approvals pending"
          description="Agent escalations will surface here when a human decision is required."
          eyebrow="Review queue"
        />
      ) : (
        visibleApprovals.map((approval) => (
          <div key={approval.approval_id} className="space-y-2">
            <ApprovalCard approval={approval} onDecide={handleDecide} />
            {errorById[approval.approval_id] ? (
              <div className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
                {errorById[approval.approval_id]}
              </div>
            ) : null}
          </div>
        ))
      )}
    </div>
  );
}
