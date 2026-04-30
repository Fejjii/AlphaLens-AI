import { cn } from "@/lib/utils";

export function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-[0.875rem] bg-gradient-to-r from-muted/70 via-muted to-muted/70",
        className,
      )}
      {...props}
    />
  );
}
