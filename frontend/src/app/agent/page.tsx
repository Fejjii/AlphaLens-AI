import { ChatPanel } from "@/components/chat/ChatPanel";
import { PageHeader } from "@/components/layout/PageHeader";

export default function AgentChatPage() {
  return (
    <div>
      <PageHeader
        title="Agent Chat"
        description="Ask the AlphaLens agent about portfolio, risk, research, or approvals."
      />
      <ChatPanel />
    </div>
  );
}
