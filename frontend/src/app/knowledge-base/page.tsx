import { Library } from "lucide-react";

import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";

export default function KnowledgeBasePage() {
  return (
    <div>
      <PageHeader
        title="Knowledge Base"
        description="Documents indexed for retrieval-augmented generation."
      />
      <EmptyState
        icon={Library}
        title="Knowledge base is empty"
        description="Upload research notes, filings, transcripts, or policy docs. AlphaLens uses them as retrieval context so chat answers and investigations can cite grounded evidence instead of improvising."
        eyebrow="Retrieval corpus"
        action={<Button variant="outline">Document ingestion coming soon</Button>}
      />
    </div>
  );
}
