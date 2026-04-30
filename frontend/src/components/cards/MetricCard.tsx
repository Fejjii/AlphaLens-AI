import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string;
  delta?: {
    value: string;
    direction: "up" | "down" | "flat";
  };
  hint?: string;
}

export function MetricCard({ label, value, delta, hint }: MetricCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-3">
        <CardTitle className="section-label">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="tabular text-[1.75rem] font-semibold tracking-tight text-foreground">
          {value}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          {delta && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 font-medium",
                delta.direction === "up" && "text-success",
                delta.direction === "down" && "text-danger",
                delta.direction === "flat" && "text-muted-foreground",
                delta.direction === "up" && "border-success/20 bg-success/10",
                delta.direction === "down" && "border-danger/20 bg-danger/10",
                delta.direction === "flat" && "border-border/70 bg-muted/50",
              )}
            >
              {delta.direction === "up" && <ArrowUpRight className="h-3 w-3" />}
              {delta.direction === "down" && <ArrowDownRight className="h-3 w-3" />}
              <span className="tabular">{delta.value}</span>
            </span>
          )}
          {hint && <span className="text-muted-foreground">{hint}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
