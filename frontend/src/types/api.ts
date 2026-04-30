// Mirrors backend Pydantic schemas in `alphalens.schemas`.
// Keep in sync manually for now; consider generating via openapi-typescript later.

export interface Money {
  amount: string;
  currency: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  environment: string;
}

export interface ErrorResponse {
  code: string;
  message: string;
  details?: unknown;
}

export interface Position {
  symbol: string;
  quantity: string;
  average_cost: Money;
  market_value: Money;
  unrealized_pnl: Money;
  weight: number;
}

export interface RiskMetric {
  name: string;
  value: number;
  unit?: string | null;
}

export interface PortfolioSummary {
  portfolio_id: string;
  as_of: string;
  nav: Money;
  day_pnl: Money;
  day_pnl_pct: number;
  positions: Position[];
  risk_metrics: RiskMetric[];
}

export type Recommendation =
  | "inform"
  | "hold"
  | "buy"
  | "sell"
  | "trim"
  | "rebalance"
  | "escalate";

export type ApprovalActionType =
  | "buy"
  | "sell"
  | "trim"
  | "rebalance"
  | "escalate"
  | "report";

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "needs_more_analysis"
  | "cancelled";

export interface EvidenceItem {
  tool: string;
  summary: string;
  data?: unknown;
}

export interface Approval {
  approval_id: string;
  created_at: string;
  status: ApprovalStatus;
  action_type: ApprovalActionType;
  asset?: string | null;
  recommendation: Recommendation;
  rationale: string;
  evidence: EvidenceItem[];
  risk_level?: string | null;
  confidence?: number | null;
  reviewer_note?: string | null;
  decided_at?: string | null;
}

export type ApprovalDecisionStatus = Extract<
  ApprovalStatus,
  "approved" | "rejected" | "needs_more_analysis" | "cancelled"
>;

export interface ApprovalDecisionPayload {
  status: ApprovalDecisionStatus;
  reviewer_note?: string | null;
}

export type ChatRole = "user" | "assistant" | "system" | "tool";

export interface ChatMessage {
  role: ChatRole;
  content: string;
}

export interface Citation {
  source_id: string;
  title: string;
  url?: string | null;
  snippet?: string | null;
  score?: number | null;
}

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface AgentDecision {
  intent: string;
  recommendation: Recommendation;
  reasoning: string[];
  evidence: EvidenceItem[];
  requires_approval: boolean;
  approval_id?: string | null;
  risk_level: RiskLevel;
  confidence: number;
}

export interface ChatRequest {
  conversation_id?: string | null;
  messages: ChatMessage[];
}

export interface ChatResponse {
  conversation_id: string;
  response_id: string;
  message: ChatMessage;
  response_language?: string | null;
  citations: Citation[];
  used_tools: string[];
  decision?: AgentDecision | null;
}

export interface TranscriptionResult {
  text: string;
  language?: string | null;
  provider: string;
}

export type UsageEventType =
  | "llm_call"
  | "llm_fallback"
  | "llm_error"
  | "tool_call"
  | "tool_error"
  | "cache_hit"
  | "feedback_submitted"
  | "report_generated";

export interface UsageEvent {
  usage_id: string;
  created_at: string;
  conversation_id?: string | null;
  event_type: UsageEventType;
  provider: string;
  model?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost_usd?: number | null;
  tool_name?: string | null;
  metadata: Record<string, unknown>;
}

export interface UsageSummary {
  total_events: number;
  total_tokens: number;
  estimated_cost_usd: number;
  tool_calls: number;
  llm_calls: number;
}

export type FeedbackRating = "thumbs_up" | "thumbs_down";
export type FeedbackCategory = "accuracy" | "usefulness" | "clarity" | "risk" | "other";

export interface FeedbackCreate {
  conversation_id: string;
  message_id?: string | null;
  response_id?: string | null;
  rating: FeedbackRating;
  comment?: string | null;
  category?: FeedbackCategory | null;
}

export interface FeedbackResponse extends FeedbackCreate {
  id: string;
  created_at: string;
}

export interface FeedbackSummary {
  total_feedback: number;
  thumbs_up: number;
  thumbs_down: number;
  by_category: Record<string, number>;
}

export type ReportType = "investment_memo" | "risk_review" | "portfolio_update";
export type ReportStatus = "draft" | "generated";

export interface ReportSection {
  key: string;
  title: string;
  content: string;
  bullets: string[];
}

export interface ReportCreate {
  title?: string | null;
  report_type: ReportType;
  prompt: string;
  conversation_id?: string | null;
  source_response_id?: string | null;
  ticker?: string | null;
}

export interface ReportResponse {
  id: string;
  title: string;
  report_type: ReportType;
  conversation_id?: string | null;
  source_response_id?: string | null;
  ticker?: string | null;
  status: ReportStatus;
  sections: ReportSection[];
  evidence: EvidenceItem[];
  citations: string[];
  created_at: string;
  updated_at: string;
}

export interface ReportSummary {
  total_reports: number;
  generated_reports: number;
  by_type: Record<string, number>;
}

export type ScenarioType =
  | "price_shock"
  | "rate_shock"
  | "sector_shock"
  | "fx_shock"
  | "rebalance";

export interface ScenarioImpactItem {
  symbol: string;
  sector?: string | null;
  current_value_usd: number;
  shocked_value_usd: number;
  delta_usd: number;
  delta_pct: number;
}

export interface ScenarioCreate {
  title?: string | null;
  scenario_type: ScenarioType;
  ticker?: string | null;
  sector?: string | null;
  shock_percent?: number | null;
  rate_bps?: number | null;
  currency?: string | null;
  assumptions?: string[];
}

export interface ScenarioResponse {
  id: string;
  title: string;
  scenario_type: ScenarioType;
  ticker?: string | null;
  sector?: string | null;
  shock_percent?: number | null;
  rate_bps?: number | null;
  currency?: string | null;
  assumptions: string[];
  portfolio_impact: number;
  affected_holdings: ScenarioImpactItem[];
  risk_level: string;
  recommendation: string;
  approval_required: boolean;
  created_at: string;
}

export interface ScenarioSummary {
  total_scenarios: number;
  by_type: Record<string, number>;
}
