import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] transition-colors",
  {
    variants: {
      variant: {
        default: "border-primary/20 bg-primary/12 text-primary",
        outline: "border-border/80 bg-background/40 text-foreground",
        success: "border-success/20 bg-success/12 text-success",
        danger: "border-danger/20 bg-danger/12 text-danger",
        warning: "border-warning/20 bg-warning/12 text-warning",
        muted: "border-border/70 bg-muted/70 text-muted-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
