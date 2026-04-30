import { AlertTriangle, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorBannerProps {
  title?: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function ErrorBanner({
  title = "Something needs attention",
  message,
  actionLabel,
  onAction,
  className,
}: ErrorBannerProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-[1rem] border border-danger/25 bg-danger/10 px-4 py-3 text-sm text-danger sm:flex-row sm:items-center sm:justify-between",
        className,
      )}
      role="alert"
    >
      <div className="flex min-w-0 items-start gap-3">
        <div className="mt-0.5 rounded-xl bg-danger/15 p-2">
          <AlertTriangle className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-foreground">{title}</div>
          <p className="mt-1 text-danger/90">{message}</p>
        </div>
      </div>
      {actionLabel && onAction ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="border-danger/30 bg-background/60"
          onClick={onAction}
        >
          <RefreshCcw className="h-3.5 w-3.5" />
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
