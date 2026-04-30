import type {
  Approval,
  ApprovalDecisionPayload,
  ChatRequest,
  ChatResponse,
  FeedbackCreate,
  FeedbackResponse,
  FeedbackSummary,
  HealthStatus,
  PortfolioSummary,
  ReportCreate,
  ReportResponse,
  ReportSummary,
  ScenarioCreate,
  ScenarioResponse,
  ScenarioSummary,
  TranscriptionResult,
  UsageEvent,
  UsageSummary,
} from "@/types/api";
import {
  mockApprovals,
  mockChatResponse,
  mockPortfolio,
  mockReports,
  mockReportSummary,
  mockScenarioSummary,
  mockScenarios,
  mockUsageEvents,
  mockUsageSummary,
} from "@/lib/mock";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";
const DEFAULT_TIMEOUT_MS = 8000;

class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...init.headers,
      },
      cache: "no-store",
    });
    if (!response.ok) {
      throw new ApiError(`Request failed: ${response.status}`, response.status);
    }
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

// Each call falls back to deterministic mock data if the backend is
// unreachable so the dashboard remains demoable in isolation.
async function withFallback<T>(promise: Promise<T>, fallback: T): Promise<T> {
  try {
    return await promise;
  } catch {
    return fallback;
  }
}

async function fetchApprovals(): Promise<Approval[]> {
  return withFallback(request<Approval[]>("/approvals"), mockApprovals);
}

async function decideApproval(
  approvalId: string,
  payload: ApprovalDecisionPayload,
): Promise<Approval> {
  return request<Approval>(`/approvals/${approvalId}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function fetchUsageSummary(): Promise<UsageSummary> {
  return withFallback(request<UsageSummary>("/usage/summary"), mockUsageSummary);
}

async function fetchUsageEvents(): Promise<UsageEvent[]> {
  return withFallback(request<UsageEvent[]>("/usage/events"), mockUsageEvents);
}

export const api = {
  health: () =>
    withFallback(request<HealthStatus>("/health"), {
      status: "mock",
      version: "0.0.0",
      environment: "mock",
    }),
  portfolioSummary: () =>
    withFallback(request<PortfolioSummary>("/portfolio/summary"), mockPortfolio),
  approvals: fetchApprovals,
  fetchApprovals,
  decideApproval,
  fetchUsageSummary,
  fetchUsageEvents,
  submitFeedback: (payload: FeedbackCreate) =>
    request<FeedbackResponse>("/feedback", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  fetchFeedbackSummary: () =>
    withFallback(request<FeedbackSummary>("/feedback/summary"), {
      total_feedback: 0,
      thumbs_up: 0,
      thumbs_down: 0,
      by_category: {},
    }),
  createReport: (payload: ReportCreate) =>
    request<ReportResponse>("/reports", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  fetchReports: () => withFallback(request<ReportResponse[]>("/reports"), mockReports),
  fetchReportSummary: () =>
    withFallback(request<ReportSummary>("/reports/summary"), mockReportSummary),
  createScenario: (payload: ScenarioCreate) =>
    request<ScenarioResponse>("/scenarios", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  fetchScenarios: () => withFallback(request<ScenarioResponse[]>("/scenarios"), mockScenarios),
  fetchScenarioSummary: () =>
    withFallback(request<ScenarioSummary>("/scenarios/summary"), mockScenarioSummary),
  usageSummary: fetchUsageSummary,
  usageEvents: fetchUsageEvents,
  chat: (payload: ChatRequest) =>
    withFallback(
      request<ChatResponse>("/agent/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
      { ...mockChatResponse, conversation_id: payload.conversation_id ?? "conv_mock" },
    ),
  transcribeSpeech: async (file: File): Promise<TranscriptionResult> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_URL}/speech/transcribe`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new ApiError(`Request failed: ${response.status}`, response.status);
    }
    return (await response.json()) as TranscriptionResult;
  },
};

export { ApiError };
