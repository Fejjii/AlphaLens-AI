import type { UsageEvent } from "@/types/api";
import { EventTypeBadge, ProviderBadge } from "@/components/ui/status-badges";

interface UsageEventsTableProps {
  events: UsageEvent[];
}

function formatTokens(value?: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString("en-US");
}

function formatCost(value?: number | null): string {
  if (value == null) return "—";
  return `$${value.toFixed(4)}`;
}

export function UsageEventsTable({ events }: UsageEventsTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="table-base min-w-[1080px]">
        <thead>
          <tr className="table-head-row">
            <th className="table-head-cell">Time</th>
            <th className="table-head-cell">Event</th>
            <th className="table-head-cell">Provider</th>
            <th className="table-head-cell">Model / Tool</th>
            <th className="table-head-cell">Tokens</th>
            <th className="table-head-cell">Estimated Cost</th>
            <th className="table-head-cell">Conversation</th>
            <th className="table-head-cell">Metadata</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.usage_id} className="table-row">
              <td className="table-cell text-muted-foreground">
                {new Date(event.created_at).toLocaleString()}
              </td>
              <td className="table-cell">
                <EventTypeBadge eventType={event.event_type} />
              </td>
              <td className="table-cell">
                <ProviderBadge provider={event.provider} />
              </td>
              <td className="table-cell text-muted-foreground">
                {event.model ?? event.tool_name ?? "—"}
              </td>
              <td className="table-cell tabular">
                <div className="flex items-center gap-2">
                  <span>{formatTokens(event.total_tokens)}</span>
                  <span className="text-xs text-muted-foreground">
                    {formatTokens(event.input_tokens)}
                    {event.output_tokens != null ? ` / ${formatTokens(event.output_tokens)}` : ""}
                  </span>
                </div>
              </td>
              <td className="table-cell tabular">{formatCost(event.estimated_cost_usd)}</td>
              <td className="table-cell text-muted-foreground">
                {event.conversation_id ?? "—"}
              </td>
              <td className="table-cell text-xs text-muted-foreground">
                <div className="max-w-[220px] space-y-1">
                  {event.tool_name && <div>tool: {event.tool_name}</div>}
                  {event.metadata && Object.keys(event.metadata).length > 0 ? (
                    <div>meta: {Object.entries(event.metadata).slice(0, 2).map(([key, value]) => `${key}=${String(value)}`).join(", ")}</div>
                  ) : (
                    <div>—</div>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
