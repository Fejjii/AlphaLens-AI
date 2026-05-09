import type {
  AgentDecision,
  ChatAnalysis,
  ReportAnalysisContext,
  ReportCreate,
  ReportMemoContext,
} from "@/types/api";

const MEMO_ANALYSIS_KEYS = [
  "intent",
  "tools_used",
  "rag_sources",
  "provider_modes",
  "data_used",
  "limitations",
  "orchestration_trace",
  "portfolio_snapshot_used",
  "policy_rules_used",
] as const;

function inferTickerFromDecision(decision: AgentDecision): string | null {
  for (const item of decision.evidence) {
    const data = item.data;
    if (typeof data !== "object" || data == null) continue;
    const record = data as Record<string, unknown>;
    const quotes = record.quotes;
    if (!Array.isArray(quotes) || quotes.length === 0) continue;
    const firstQuote = quotes[0];
    if (typeof firstQuote !== "object" || firstQuote == null) continue;
    const ticker = (firstQuote as Record<string, unknown>).ticker;
    if (typeof ticker === "string" && ticker.trim()) return ticker;
  }
  return null;
}

/** Remove keys whose value is `undefined` (recursively) so JSON matches backend expectations. */
export function stripUndefinedDeep(value: unknown): unknown {
  if (value === undefined) return undefined;
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    return value.map((item) => stripUndefinedDeep(item));
  }
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    if (v === undefined) continue;
    const inner = stripUndefinedDeep(v);
    if (inner !== undefined) {
      out[k] = inner;
    }
  }
  return out;
}

function pickMemoAnalysis(analysis: ChatAnalysis): ReportAnalysisContext {
  const row: Record<string, unknown> = {};
  for (const key of MEMO_ANALYSIS_KEYS) {
    const v = analysis[key as keyof ChatAnalysis];
    if (v !== undefined) {
      row[key] = v as unknown;
    }
  }
  return row as unknown as ReportAnalysisContext;
}

/**
 * Builds a POST /reports payload aligned with backend ReportCreate / memo_context
 * (only analysis fields allowed on ReportAnalysisContext; no ChatAnalysis extras).
 */
export function buildInvestmentMemoReportPayload(params: {
  conversationId: string;
  responseId: string;
  decision: AgentDecision;
  analysis: ChatAnalysis;
  userPrompt?: string | null;
}): ReportCreate {
  const ticker = inferTickerFromDecision(params.decision);
  const memo_context: ReportMemoContext = {
    user_prompt: params.userPrompt?.trim() || undefined,
    agent_final_answer: params.analysis.final_answer?.trim(),
    answer_type: "investment_decision",
    decision: {
      action: params.decision.recommendation,
      recommendation: params.decision.recommendation,
      risk_level: params.decision.risk_level,
      confidence: params.decision.confidence,
      approval_required: params.decision.requires_approval,
      approval_id: params.decision.approval_id ?? undefined,
      approval_required_reason: params.decision.approval_required_reason ?? undefined,
      key_reasoning: params.decision.reasoning,
      key_evidence: params.decision.evidence,
      policy_flags: params.decision.policy_flags ?? [],
    },
    analysis: pickMemoAnalysis(params.analysis),
    ticker_or_subject: ticker ?? undefined,
  };
  const raw: ReportCreate = {
    report_type: "investment_memo",
    conversation_id: params.conversationId,
    source_response_id: params.responseId,
    ticker: ticker ?? undefined,
    prompt: "Generate an investment memo from this agent decision.",
    memo_context,
  };
  return stripUndefinedDeep(raw) as ReportCreate;
}
