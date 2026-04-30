import { Card, CardContent } from "@/components/ui/card";

interface EmptyStateProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  eyebrow?: string;
  action?: React.ReactNode;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  eyebrow = "Nothing here yet",
  action,
}: EmptyStateProps) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center gap-4 px-6 py-16 text-center md:py-20">
        <div className="rounded-[1.25rem] border border-border/70 bg-background/70 p-3 text-primary shadow-inner shadow-black/10">
          <Icon className="h-5 w-5" />
        </div>
        <div className="section-label">{eyebrow}</div>
        <div className="text-lg font-semibold tracking-tight">{title}</div>
        <p className="max-w-md text-sm leading-6 text-muted-foreground">{description}</p>
        {action ? <div className="pt-1">{action}</div> : null}
      </CardContent>
    </Card>
  );
}
