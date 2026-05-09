import type {
  Approval,
  ChatResponse,
  PortfolioSummary,
  ReportResponse,
  ReportSummary,
  ScenarioResponse,
  ScenarioSummary,
  UsageEvent,
  UsageSummary,
} from "@/types/api";

export const mockPortfolio: PortfolioSummary = {
  portfolio_id: "demo",
  as_of: new Date().toISOString(),
  nav: { amount: "667500.00", currency: "USD" },
  day_pnl: { amount: "4820.50", currency: "USD" },
  day_pnl_pct: 0.0072,
  positions: [
    {
      symbol: "AAPL",
      quantity: "1200",
      average_cost: { amount: "145.20", currency: "USD" },
      market_value: { amount: "228000.00", currency: "USD" },
      unrealized_pnl: { amount: "53760.00", currency: "USD" },
      weight: 0.34,
    },
    {
      symbol: "MSFT",
      quantity: "600",
      average_cost: { amount: "298.50", currency: "USD" },
      market_value: { amount: "252000.00", currency: "USD" },
      unrealized_pnl: { amount: "72900.00", currency: "USD" },
      weight: 0.38,
    },
    {
      symbol: "NVDA",
      quantity: "250",
      average_cost: { amount: "420.00", currency: "USD" },
      market_value: { amount: "187500.00", currency: "USD" },
      unrealized_pnl: { amount: "82500.00", currency: "USD" },
      weight: 0.28,
    },
  ],
  risk_metrics: [
    { name: "sharpe", value: 1.42 },
    { name: "max_drawdown", value: -0.087, unit: "ratio" },
    { name: "beta", value: 1.08 },
    { name: "volatility_annualized", value: 0.214, unit: "ratio" },
  ],
};

export const mockApprovals: Approval[] = [
  {
    approval_id: "apv_001",
    user_id: "user_demo",
    created_at: new Date().toISOString(),
    status: "pending",
    action_type: "buy",
    asset: "NVDA",
    recommendation: "buy",
    rationale:
      "Q3 earnings beat consensus by 12%. Data-center revenue accelerating; technicals confirm breakout above 200d MA. Increasing exposure aligns with growth sleeve mandate.",
    evidence: [
      { tool: "market_data", summary: "NVDA momentum score 0.82 (top decile)" },
      { tool: "rag", summary: "3 internal notes corroborate semis H2 thesis" },
    ],
    risk_level: "medium",
    confidence: 0.78,
    reviewer_note: null,
    decided_at: null,
  },
  {
    approval_id: "apv_002",
    user_id: "user_demo",
    created_at: new Date().toISOString(),
    status: "pending",
    action_type: "rebalance",
    asset: "Growth Sleeve",
    recommendation: "rebalance",
    rationale:
      "Drift exceeds 3% on 4 positions. Trim MSFT, add JPM and XOM to restore policy weights and reduce single-name concentration.",
    evidence: [
      { tool: "portfolio", summary: "MSFT weight 38% vs 32% target" },
    ],
    risk_level: "low",
    confidence: 0.91,
    reviewer_note: null,
    decided_at: null,
  },
  {
    approval_id: "apv_003",
    user_id: "user_demo",
    created_at: new Date().toISOString(),
    status: "pending",
    action_type: "trim",
    asset: "AAPL",
    recommendation: "trim",
    rationale:
      "AAPL position approaching concentration limit. Trim 10% to lock in gains and free up risk budget for higher-conviction names.",
    evidence: [
      { tool: "risk", summary: "Concentration HHI 0.31 (above 0.28 threshold)" },
    ],
    risk_level: "high",
    confidence: 0.64,
    reviewer_note: null,
    decided_at: null,
  },
];

export const mockChatResponse: ChatResponse = {
  conversation_id: "conv_demo",
  response_id: "msg_demo",
  answer_type: "app_help",
  routing: {
    answer_type: "app_help",
    intent: "app_capability",
    confidence: 1,
    language: "en",
    reason: "mock",
    suggested_tools: [],
    router_source: "mock",
  },
  message: {
    role: "assistant",
    content:
      "I'm AlphaLens, your investment intelligence copilot. Ask me about your portfolio, research notes, risk metrics, or pending approvals.",
  },
  citations: [],
  used_tools: [],
  decision: null,
  analysis: {
    intent: "general",
    final_answer:
      "I'm AlphaLens, your investment intelligence copilot. Ask me about your portfolio, research notes, risk metrics, or pending approvals.",
    recommendation: "inform",
    confidence: 0.7,
    approval_required: false,
    approval_reason: null,
    tools_used: [],
    provider_modes: [],
    evidence_items: [],
    rag_sources: [],
    rag_status: "No RAG retrieval was triggered because intent was general.",
    portfolio_snapshot_used: "synthetic_portfolio_holdings.csv",
    policy_rules_used: [],
    data_freshness: "Synthetic snapshot",
    data_used: [],
    limitations: ["Demo response"],
    disclaimer: "Demo mode",
    orchestration_trace: {},
  },
};

export const mockUsageSummary: UsageSummary = {
  total_events: 24,
  total_tokens: 18420,
  estimated_cost_usd: 0.0428,
  tool_calls: 11,
  llm_calls: 13,
};

export const mockUsageEvents: UsageEvent[] = [
  {
    usage_id: "use_001",
    created_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    conversation_id: "conv_demo",
    event_type: "llm_call",
    provider: "openai",
    model: "gpt-4o-mini",
    input_tokens: 780,
    output_tokens: 220,
    total_tokens: 1000,
    estimated_cost_usd: 0.00025,
    tool_name: null,
    metadata: { operation: "classify_intent" },
  },
  {
    usage_id: "use_002",
    created_at: new Date(Date.now() - 90 * 1000).toISOString(),
    conversation_id: "conv_demo",
    event_type: "tool_call",
    provider: "market_data",
    model: null,
    input_tokens: null,
    output_tokens: null,
    total_tokens: 0,
    estimated_cost_usd: 0,
    tool_name: "market_quote",
    metadata: { tickers: ["NVDA"] },
  },
  {
    usage_id: "use_003",
    created_at: new Date(Date.now() - 45 * 1000).toISOString(),
    conversation_id: "conv_demo",
    event_type: "cache_hit",
    provider: "cache",
    model: null,
    input_tokens: null,
    output_tokens: null,
    total_tokens: 0,
    estimated_cost_usd: 0,
    tool_name: null,
    metadata: { namespace: "market_data" },
  },
];

export const mockReports: ReportResponse[] = [
  {
    id: "rpt_demo",
    user_id: "user_demo",
    title: "Investment Memo · NVDA",
    report_type: "investment_memo",
    conversation_id: "conv_demo",
    source_response_id: "msg_demo",
    ticker: "NVDA",
    status: "generated",
    sections: [
      {
        key: "executive_summary",
        title: "Executive Summary",
        content: "Deterministic mock memo generated for demo continuity.",
        bullets: ["Demo-only content", "No execution actions"],
      },
    ],
    evidence: [],
    citations: ["market_data", "risk"],
    disclaimer: "Demo disclaimer",
    limitations: ["Demo limitation"],
    evidence_count: 0,
    policy_flags: [],
    approval_required_reason: null,
    memo_metadata: {
      limited_context: true,
      rag_sources_count: 0,
      tools_used: [],
      fallback_used: true,
      generated_sections: ["executive_summary"],
      approval_id: null,
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
];

export const mockReportSummary: ReportSummary = {
  total_reports: 1,
  generated_reports: 1,
  by_type: {
    investment_memo: 1,
  },
};

export const mockScenarios: ScenarioResponse[] = [
  {
    id: "scn_demo",
    user_id: "user_demo",
    title: "Price shock · NVDA",
    scenario_type: "price_shock",
    ticker: "NVDA",
    assumptions: ["Deterministic synthetic holdings snapshot used."],
    portfolio_impact: -18750,
    affected_holdings: [
      {
        symbol: "NVDA",
        sector: "Semiconductors",
        current_value_usd: 187500,
        shocked_value_usd: 168750,
        delta_usd: -18750,
        delta_pct: -0.1,
      },
    ],
    risk_level: "medium",
    recommendation: "Use as a planning scenario; no execution implied.",
    approval_required: false,
    created_at: new Date().toISOString(),
  },
];

export const mockScenarioSummary: ScenarioSummary = {
  total_scenarios: 1,
  by_type: {
    price_shock: 1,
  },
};

// Note: when `decision` is non-null in real responses the backend always
// sends `risk_level` and `confidence`, so frontend code can read them
// directly without optional-chaining or fallbacks.

