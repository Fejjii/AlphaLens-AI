import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface UsageMetricCardProps {
  label: string;
  value: string;
  hint?: string;
  href?: string;
}

export function UsageMetricCard({ label, value, hint, href }: UsageMetricCardProps) {
  const content = (
    <Card className="transition-colors hover:border-primary/30">
      <CardHeader className="pb-3">
        <CardTitle className="section-label">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="tabular text-[1.75rem] font-semibold tracking-tight text-foreground">
          {value}
        </div>
        {hint ? <p className="mt-3 text-xs leading-5 text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  );

  if (!href) return content;
  return (
    <Link href={href} className="block">
      {content}
    </Link>
  );
}
