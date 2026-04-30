import { AlertTriangle, Info, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Severity = "info" | "warning" | "danger";

interface AlertCardProps {
  severity: Severity;
  title: string;
  description: string;
  source?: string;
  timestamp?: string;
}

const ICONS: Record<Severity, React.ComponentType<{ className?: string }>> = {
  info: Info,
  warning: AlertTriangle,
  danger: ShieldAlert,
};

const VARIANT: Record<Severity, "default" | "warning" | "danger"> = {
  info: "default",
  warning: "warning",
  danger: "danger",
};

export function AlertCard({ severity, title, description, source, timestamp }: AlertCardProps) {
  const Icon = ICONS[severity];
  return (
    <Card>
      <CardContent className="flex items-start gap-3 p-4">
        <div
          className={cn(
            "mt-0.5 rounded-md p-2",
            severity === "danger" && "bg-danger/15 text-danger",
            severity === "warning" && "bg-warning/15 text-warning",
            severity === "info" && "bg-primary/15 text-primary",
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{title}</span>
            <Badge variant={VARIANT[severity]} className="capitalize">
              {severity}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{description}</p>
          {(source || timestamp) && (
            <div className="text-xs text-muted-foreground">
              {source && <span>{source}</span>}
              {source && timestamp && <span> · </span>}
              {timestamp && <span>{timestamp}</span>}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
