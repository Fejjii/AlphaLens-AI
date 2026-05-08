import { ShieldAlert, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type {
  ApprovalStatus,
  Recommendation,
  RiskLevel,
  UsageEventType,
} from "@/types/api";

type BadgeVariant =
  | "default"
  | "success"
  | "danger"
  | "warning"
  | "muted"
  | "outline";

const RECOMMENDATION_VARIANT: Record<Recommendation, BadgeVariant> = {
  buy: "success",
  sell: "danger",
  trim: "warning",
  rebalance: "default",
  escalate: "danger",
  hold: "muted",
  inform: "muted",
  needs_more_analysis: "warning",
};

const APPROVAL_STATUS_VARIANT: Record<ApprovalStatus, BadgeVariant> = {
  pending: "warning",
  approved: "success",
  rejected: "danger",
  needs_more_analysis: "default",
  cancelled: "muted",
};

const APPROVAL_STATUS_LABEL: Record<ApprovalStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  needs_more_analysis: "Needs more analysis",
  cancelled: "Cancelled",
};

const EVENT_VARIANT: Record<UsageEventType, BadgeVariant> = {
  llm_call: "default",
  llm_fallback: "warning",
  llm_error: "danger",
  tool_call: "success",
  tool_error: "danger",
  cache_hit: "muted",
  feedback_submitted: "outline",
  report_generated: "success",
};

export function recommendationBadgeVariant(
  recommendation: Recommendation,
): BadgeVariant {
  return RECOMMENDATION_VARIANT[recommendation] ?? "default";
}

export function riskBadgeVariant(
  level: string | RiskLevel | null | undefined,
): BadgeVariant {
  if (level === "low") return "success";
  if (level === "medium") return "warning";
  return "danger";
}

export function statusBadgeVariant(status: ApprovalStatus): BadgeVariant {
  return APPROVAL_STATUS_VARIANT[status] ?? "muted";
}

export function eventBadgeVariant(eventType: UsageEventType): BadgeVariant {
  return EVENT_VARIANT[eventType] ?? "muted";
}

export function StatusBadge({ status }: { status: ApprovalStatus }) {
  return (
    <Badge variant={statusBadgeVariant(status)} className="capitalize">
      {APPROVAL_STATUS_LABEL[status]}
    </Badge>
  );
}

export function RecommendationBadge({
  recommendation,
}: {
  recommendation: Recommendation;
}) {
  return (
    <Badge
      variant={recommendationBadgeVariant(recommendation)}
      className="uppercase"
    >
      {recommendation}
    </Badge>
  );
}

export function RiskBadge({
  level,
}: {
  level: string | RiskLevel | null | undefined;
}) {
  if (!level) return null;

  return (
    <Badge variant={riskBadgeVariant(level)} className="capitalize">
      {level} risk
    </Badge>
  );
}

export function ConfidenceBadge({ value }: { value: number }) {
  return (
    <Badge variant="muted" className="tabular">
      {(value * 100).toFixed(0)}% confidence
    </Badge>
  );
}

export function ApprovalModeBadge({
  requiresApproval,
}: {
  requiresApproval: boolean;
}) {
  return (
    <Badge
      variant={requiresApproval ? "warning" : "success"}
      className="gap-1.5"
    >
      {requiresApproval ? (
        <ShieldAlert className="h-3 w-3" />
      ) : (
        <ShieldCheck className="h-3 w-3" />
      )}
      {requiresApproval ? "Human review required" : "Within auto-approval"}
    </Badge>
  );
}

export function ProviderBadge({ provider }: { provider: string }) {
  return (
    <Badge variant="outline" className="capitalize">
      {provider}
    </Badge>
  );
}

export function EventTypeBadge({ eventType }: { eventType: UsageEventType }) {
  return (
    <Badge variant={eventBadgeVariant(eventType)} className="capitalize">
      {eventType.replaceAll("_", " ")}
    </Badge>
  );
}
