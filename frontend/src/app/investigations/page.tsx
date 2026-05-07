import { Search } from "lucide-react";
import Link from "next/link";

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
        action={
          <Button asChild variant="outline">
            <Link href="/agent?mode=investigation&prompt=Investigate%20portfolio%20risk%20using%20portfolio%2C%20policy%2C%20market%2C%20news%2C%20macro%2C%20SEC%2C%20and%20RAG%20context.">
              Start from agent chat
            </Link>
          </Button>
        }
      />
    </div>
  );
}
