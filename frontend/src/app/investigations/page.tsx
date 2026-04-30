import { Search } from "lucide-react";

import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";

export default function InvestigationsPage() {
  return (
    <div>
      <PageHeader
        title="Investigations"
        description="Multi-step agent investigations with tool traces and citations."
      />
      <EmptyState
        icon={Search}
        title="No investigations yet"
        description="Multi-step investigations will appear here when AlphaLens chains portfolio, policy, market, news, macro, SEC, and retrieval tools into a single reviewable storyline."
        eyebrow="Investigation timeline"
        action={<Button variant="outline">Start from agent chat</Button>}
      />
    </div>
  );
}
