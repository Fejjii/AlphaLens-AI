"use client";

import { useState } from "react";
import { Check, Clock3, HelpCircle, Loader2, ShieldAlert, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  ConfidenceBadge,
  RecommendationBadge,
  RiskBadge,
  StatusBadge,
} from "@/components/ui/status-badges";
import { cn } from "@/lib/utils";
import type {
  Approval,
  ApprovalDecisionStatus,
} from "@/types/api";

interface ApprovalCardProps {
  approval: Approval;
  onDecide?: (
    approvalId: string,
    status: ApprovalDecisionStatus,
  ) => Promise<void> | void;
}

export function ApprovalCard({ approval, onDecide }: ApprovalCardProps) {
  const [pendingAction, setPendingAction] = useState<ApprovalDecisionStatus | null>(
    null,
  );

  const isTerminal = approval.status !== "pending";

  const handleClick = async (status: ApprovalDecisionStatus) => {
    if (!onDecide || pendingAction || isTerminal) return;
    setPendingAction(status);
    try {
      await onDecide(approval.approval_id, status);
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <Card className="border-border/70 bg-card/80">
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <div className="section-label">Human review required</div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate text-base font-semibold tracking-tight">
                {approval.asset ?? "—"}
              </span>
              <RecommendationBadge recommendation={approval.recommendation} />
              <StatusBadge status={approval.status} />
              {approval.confidence != null ? <ConfidenceBadge value={approval.confidence} /> : null}
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="font-mono">{approval.approval_id}</span>
              <span>·</span>
              <span>{new Date(approval.created_at).toLocaleString()}</span>
            </div>
          </div>
          <RiskBadge level={approval.risk_level} />
        </div>

        <div className="rounded-[0.875rem] border border-warning/20 bg-warning/8 px-3 py-3">
          <div className="flex items-center gap-2 text-xs font-medium text-warning">
            <ShieldAlert className="h-3.5 w-3.5" />
            Human-in-the-loop checkpoint
          </div>
          <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-muted-foreground" title={approval.rationale}>
            {approval.rationale}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-3">
          <StatChip label="Confidence" value={approval.confidence != null ? `${(approval.confidence * 100).toFixed(0)}%` : "—"} />
          <StatChip label="Evidence" value={String(approval.evidence.length)} />
          <StatChip label="Decision" value={approval.status.replaceAll("_", " ")} />
        </div>

        <div className="rounded-[0.875rem] border border-border/60 bg-background/45 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5" />
            Audit trail
          </div>
          <div className="mt-2 space-y-2 text-sm">
            <div className="flex items-center justify-between gap-3 rounded-lg bg-background/60 px-3 py-2">
              <span className="text-muted-foreground">Request created</span>
              <span className="tabular text-foreground">
                {new Date(approval.created_at).toLocaleString()}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-lg bg-background/60 px-3 py-2">
              <span className="text-muted-foreground">Current status</span>
              <span className="capitalize text-foreground">
                {approval.status.replaceAll("_", " ")}
              </span>
            </div>
            {approval.decided_at ? (
              <div className="flex items-center justify-between gap-3 rounded-lg bg-background/60 px-3 py-2">
                <span className="text-muted-foreground">Decision recorded</span>
                <span className="tabular text-foreground">
                  {new Date(approval.decided_at).toLocaleString()}
                </span>
              </div>
            ) : null}
          </div>
        </div>

        <div className="grid gap-2 pt-1 sm:grid-cols-3">
          <ActionButton
            label="Approve"
            icon={Check}
            variant="default"
            disabled={isTerminal || (pendingAction !== null && pendingAction !== "approved")}
            loading={pendingAction === "approved"}
            onClick={() => handleClick("approved")}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
          />
          <ActionButton
            label="Reject"
            icon={X}
            variant="outline"
            disabled={isTerminal || (pendingAction !== null && pendingAction !== "rejected")}
            loading={pendingAction === "rejected"}
            onClick={() => handleClick("rejected")}
            className="border-danger/30 text-danger hover:bg-danger/10 hover:text-danger"
          />
          <ActionButton
            label="More Analysis"
            icon={HelpCircle}
            variant="ghost"
            disabled={
              isTerminal ||
              (pendingAction !== null && pendingAction !== "needs_more_analysis")
            }
            loading={pendingAction === "needs_more_analysis"}
            onClick={() => handleClick("needs_more_analysis")}
            className="hover:bg-warning/10 hover:text-warning"
          />
        </div>
      </CardContent>
    </Card>
  );
}

function StatChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[0.875rem] border border-border/60 bg-background/60 px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

interface ActionButtonProps {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  variant: "default" | "outline" | "ghost";
  disabled: boolean;
  loading: boolean;
  onClick: () => void;
  className?: string;
}

function ActionButton({
  label,
  icon: Icon,
  variant,
  disabled,
  loading,
  onClick,
  className,
}: ActionButtonProps) {
  return (
    <Button
      size="sm"
      variant={variant}
      onClick={onClick}
      disabled={disabled}
      className={cn("gap-1.5", className)}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <Icon className="h-3.5 w-3.5" />
      )}
      <span className="truncate">{label}</span>
    </Button>
  );
}
