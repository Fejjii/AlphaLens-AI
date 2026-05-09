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
  | "needs_more_analysis"
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
  user_id: string;
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
  metadata?: Record<string, unknown>;
}

export interface Citation {
  source_id: string;
  title: string;
  url?: string | null;
  snippet?: string | null;
  score?: number | null;
}

export interface ProviderMode {
  name: string;
  mode: string;
  reason?: string | null;
}

export interface RAGSource {
  document_title: string;
  chunk_id: string;
  score: number;
  snippet: string;
  source?: string | null;
}

export interface EvidenceSource {
  title: string;
  detail: string;
  source_type: string;
}

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface AgentDecision {
  intent: string;
  recommendation: Recommendation;
  reasoning: string[];
  evidence: EvidenceItem[];
  disclaimer?: string | null;
  limitations?: string[];
  requires_approval: boolean;
  approval_id?: string | null;
  risk_level: RiskLevel;
  confidence: number;
  evidence_count?: number;
  approval_required_reason?: string | null;
  policy_flags?: string[];
}

export interface ChatRequest {
  conversation_id?: string | null;
  messages: ChatMessage[];
}

export type ChatAnswerType =
  | "investment_decision"
  | "app_help"
  | "out_of_scope"
  | "clarification";

export interface ChatRouting {
  answer_type: string;
  intent: string;
  confidence: number;
  language: string;
  reason: string;
  suggested_tools: string[];
  router_source?: string | null;
}

export interface ChatResponse {
  conversation_id: string;
  response_id: string;
  message: ChatMessage;
  answer_type: ChatAnswerType;
  routing: ChatRouting;
  response_language?: string | null;
  citations: Citation[];
  used_tools: string[];
  decision?: AgentDecision | null;
  analysis: {
    intent: string;
    final_answer: string;
    recommendation: Recommendation;
    confidence: number;
    approval_required: boolean;
    approval_reason?: string | null;
    tools_used: string[];
    provider_modes: ProviderMode[];
    evidence_items: EvidenceSource[];
    rag_sources: RAGSource[];
    rag_status?: string | null;
    retrieval_mode?: string | null;
    portfolio_snapshot_used?: string | null;
    policy_rules_used: string[];
    data_freshness?: string | null;
    data_used: string[];
    limitations: string[];
    disclaimer?: string | null;
    orchestration_trace: Record<string, unknown>;
  };
  investigation_id?: string | null;
}

/** Analysis payload from agent chat; alias for memo/report builders. */
export type ChatAnalysis = ChatResponse["analysis"];

export type InvestigationStatus =
  | "open"
  | "completed"
  | "needs_more_analysis"
  | "approved"
  | "rejected";

export interface Investigation {
  id: string;
  user_id: string;
  conversation_id: string;
  source_response_id: string;
  title: string;
  status: InvestigationStatus;
  intent: string;
  subject?: string | null;
  created_at: string;
  updated_at: string;
  summary: string;
  recommendation: Recommendation;
  risk_level?: string | null;
  confidence?: number | null;
  tools_used: string[];
  evidence_items: Array<{ title: string; detail: string; source_type: string }>;
  rag_sources: RAGSource[];
  provider_modes: ProviderMode[];
  data_used: string[];
  orchestration_trace: Record<string, unknown>;
  approval_id?: string | null;
  report_id?: string | null;
  limitations: string[];
}

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationDetail {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  metadata: Record<string, unknown>[];
}

export type SpeechProviderMode = "real" | "fallback";

export interface TranscriptionResult {
  request_id?: string | null;
  transcript: string;
  detected_language?: string | null;
  response_language?: string | null;
  provider_mode?: SpeechProviderMode | null;
  confidence?: number | null;
  fallback_reason?: string | null;
  demo_transcript?: string | null;
  message?: string | null;
  fallback_used?: boolean | null;
  openai_called?: boolean | null;
  openai_response_received?: boolean | null;
}

export interface SpeechCapabilities {
  supported_mime_types: string[];
  max_upload_mb: number;
  supported_languages: string[];
  provider_mode: SpeechProviderMode;
  openai_key_configured: boolean;
  microphone_transcription_available: boolean;
  message: string;
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
  user_id?: string | null;
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

export interface RuntimeProviderStatus {
  name: string;
  status: "real" | "fallback" | "connected" | "disconnected" | "memory_fallback";
  reason?: string | null;
}

export interface RuntimeStatus {
  workspace_mode: "demo" | "live";
  providers: RuntimeProviderStatus[];
  data_sources: Record<string, string>;
}

export interface KnowledgeDocument {
  document_id: string;
  document_title: string;
  source: string;
  file_type: string;
  chunk_count: number;
  indexed_at: string;
  collection: string;
  status: string;
}

export interface KnowledgeStats {
  document_count: number;
  chunk_count: number;
  collection: string;
  vector_mode: string;
  seeded_documents: number;
  uploaded_documents: number;
  seeded_source_titles: string[];
  uploaded_source_titles: string[];
}

export interface KnowledgeUploadResponse {
  document: KnowledgeDocument;
  accepted_file_types: string[];
  max_file_size_bytes: number;
}

export interface KnowledgeSearchResult {
  document_id: string;
  document_title: string;
  chunk_id: string;
  source: string;
  score: number;
  snippet: string;
  section?: string | null;
}

export interface KnowledgeSearchResponse {
  query: string;
  k: number;
  results: KnowledgeSearchResult[];
  retrieval_mode: string;
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
  user_id: string;
  created_at: string;
}

export type UserRole = "user" | "admin" | "reviewer";
export type UserPlan = "free" | "pro" | "team";

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  plan: UserPlan;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string | null;
  token_type: "bearer";
  expires_in: number;
  user: UserProfile;
}

export interface PlanLimits {
  monthly_chats?: number | null;
  monthly_reports?: number | null;
  monthly_scenarios?: number | null;
  monthly_speech_uploads?: number | null;
  monthly_estimated_cost_usd?: number | null;
}

export interface PlanCapabilities {
  tools: string[];
  models: string[];
}

export interface PlanResponse {
  plan: UserPlan;
  limits: PlanLimits;
  capabilities: PlanCapabilities;
  description: string;
}

export interface PlanUsage {
  plan: UserPlan;
  monthly_usage: Record<string, number>;
  remaining_quota: Record<string, number | null>;
  limits: PlanLimits;
  capabilities: PlanCapabilities;
  current_month: string;
  /** UTC rollover instant for monthly usage counters (ISO-8601). */
  quota_reset_at: string;
}

export interface FeedbackSummary {
  total_feedback: number;
  thumbs_up: number;
  thumbs_down: number;
  by_category: Record<string, number>;
}

export interface RecentFeedbackItem {
  response_id?: string | null;
  rating: FeedbackRating;
  category?: FeedbackCategory | null;
  comment?: string | null;
  created_at: string;
  message_preview?: string | null;
}

export type ReportType = "investment_memo" | "risk_review" | "portfolio_update";
export type ReportStatus = "draft" | "generated";

export interface ReportSection {
  key: string;
  title: string;
  content: string;
  bullets: string[];
}

export interface ReportDecisionContext {
  action?: string | null;
  recommendation?: Recommendation | string | null;
  risk_level?: RiskLevel | string | null;
  confidence?: number | null;
  approval_required?: boolean | null;
  approval_id?: string | null;
  approval_required_reason?: string | null;
  key_reasoning: string[];
  key_evidence: EvidenceItem[];
  policy_flags: string[];
}

export interface ReportAnalysisContext {
  intent?: string | null;
  tools_used: string[];
  rag_sources: RAGSource[];
  provider_modes: ProviderMode[];
  data_used: string[];
  limitations: string[];
  orchestration_trace: Record<string, unknown>;
  portfolio_snapshot_used?: string | null;
  policy_rules_used: string[];
}

export interface ReportMemoContext {
  user_prompt?: string | null;
  agent_final_answer?: string | null;
  answer_type?: ChatAnswerType | string | null;
  decision?: ReportDecisionContext | null;
  analysis?: ReportAnalysisContext | null;
  ticker_or_subject?: string | null;
}

export interface ReportGenerationMeta {
  limited_context: boolean;
  rag_sources_count: number;
  tools_used: string[];
  fallback_used: boolean;
  generated_sections: string[];
  approval_id?: string | null;
  /** True when ``source_response_id`` was not found in server memory but memo still used client context. */
  source_lookup_failed?: boolean;
}

export interface ReportCreate {
  title?: string | null;
  report_type: ReportType;
  prompt: string;
  conversation_id?: string | null;
  source_response_id?: string | null;
  ticker?: string | null;
  memo_context?: ReportMemoContext | null;
}

export interface ReportResponse {
  id: string;
  user_id: string;
  title: string;
  report_type: ReportType;
  conversation_id?: string | null;
  source_response_id?: string | null;
  ticker?: string | null;
  status: ReportStatus;
  sections: ReportSection[];
  evidence: EvidenceItem[];
  citations: string[];
  disclaimer?: string | null;
  limitations?: string[];
  evidence_count?: number;
  policy_flags?: string[];
  approval_required_reason?: string | null;
  memo_metadata: ReportGenerationMeta;
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
  user_id: string;
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
  disclaimer?: string | null;
  limitations?: string[];
  evidence_count?: number;
  policy_flags?: string[];
  approval_required_reason?: string | null;
  created_at: string;
}

export interface ScenarioSummary {
  total_scenarios: number;
  by_type: Record<string, number>;
}
