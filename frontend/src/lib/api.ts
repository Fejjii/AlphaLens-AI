import type {
  Approval,
  ApprovalDecisionPayload,
  ChatRequest,
  ChatResponse,
  FeedbackCreate,
  RecentFeedbackItem,
  FeedbackResponse,
  FeedbackSummary,
  HealthStatus,
  KnowledgeDocument,
  KnowledgeSearchResponse,
  KnowledgeStats,
  KnowledgeUploadResponse,
  PortfolioSummary,
  ReportCreate,
  ReportResponse,
  ReportSummary,
  ScenarioCreate,
  ScenarioResponse,
  ScenarioSummary,
  SpeechCapabilities,
  TranscriptionResult,
  TokenResponse,
  UserProfile,
  PlanResponse,
  PlanUsage,
  UsageEvent,
  UsageSummary,
  RuntimeStatus,
} from "@/types/api";
import {
  mockApprovals,
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

function normalizeSpeechProviderMode(raw: unknown): NonNullable<TranscriptionResult["provider_mode"]> {
  if (raw === "real" || raw === "openai") return "real";
  return "fallback";
}

export type TranscriptionApiResult = {
  result: TranscriptionResult;
  httpStatus: number;
  clientRequestId: string;
};

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const error = typeof record.error === "string" ? record.error : null;
    if (error === "quota_exceeded") {
      const plan = typeof record.plan === "string" ? record.plan : "your";
      const limit = record.limit;
      const used = record.used;
      const resetAt = typeof record.reset_at === "string" ? record.reset_at : "";
      const base =
        typeof record.message === "string" && record.message.trim()
          ? record.message
          : `Monthly ${typeof record.feature === "string" ? record.feature.replaceAll("_", " ") : "usage"} limit reached for the ${plan} plan.`;
      const usageLine =
        limit != null && used != null
          ? ` Used ${String(used)} of ${String(limit)}.`
          : "";
      const resetLine = resetAt
        ? `\n\nQuota resets (UTC): ${resetAt}.`
        : "";
      return `${base}${usageLine}${resetLine}`.trim();
    }
    const hint = typeof record.hint === "string" ? record.hint : null;
    const message = typeof record.message === "string" ? record.message : null;
    const requestId = typeof record.request_id === "string" ? record.request_id : null;
    const providerMode = typeof record.provider_mode === "string" ? record.provider_mode : null;
    const received = typeof record.received_content_type === "string" ? record.received_content_type : null;
    if (error && message) {
      const providerText = providerMode ? ` Provider mode: ${providerMode}.` : "";
      const requestText = requestId ? ` Request: ${requestId}.` : "";
      return `${error}: ${message}.${providerText}${requestText}`.trim();
    }
    if (error && hint) {
      const receivedText = received ? ` Received: ${received}.` : "";
      const providerText = providerMode ? ` Provider mode: ${providerMode}.` : "";
      const requestText = requestId ? ` Request: ${requestId}.` : "";
      return `${error}.${receivedText} ${hint}${providerText}${requestText}`.trim();
    }
    if (message) return message;
    if (error) return error;
  }
  return null;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const hasFormDataBody = typeof FormData !== "undefined" && init.body instanceof FormData;
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: controller.signal,
      credentials: "same-origin",
      headers: {
        ...(hasFormDataBody ? {} : { "Content-Type": "application/json" }),
        Accept: "application/json",
        ...init.headers,
      },
      cache: "no-store",
    });
    if (!response.ok) {
      let detail: unknown;
      try {
        const body = (await response.json()) as { detail?: unknown };
        detail = body.detail;
      } catch {
        detail = undefined;
      }
      throw new ApiError(formatErrorDetail(detail) ?? `Request failed: ${response.status}`, response.status, detail);
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
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      throw error;
    }
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
  register: (payload: { email: string; password: string; full_name: string }) =>
    request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  login: (payload: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  refresh: () => request<TokenResponse>("/auth/refresh", { method: "POST" }),
  logout: () => request<{ logged_out: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<UserProfile>("/auth/me"),
  fetchPlans: () => request<PlanResponse[]>("/plans"),
  fetchMyPlan: () => request<PlanResponse>("/plans/me"),
  fetchMyPlanUsage: () => request<PlanUsage>("/plans/usage"),
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
  fetchRecentFeedback: () =>
    withFallback(request<RecentFeedbackItem[]>("/feedback/recent"), []),
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
  runtimeStatus: () => request<RuntimeStatus>("/runtime/status"),
  fetchKnowledgeStats: () => request<KnowledgeStats>("/knowledge/stats"),
  fetchKnowledgeDocuments: () => request<KnowledgeDocument[]>("/knowledge/documents"),
  uploadKnowledgeDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<KnowledgeUploadResponse>("/knowledge/upload", {
      method: "POST",
      body: form,
    });
  },
  searchKnowledge: (payload: { query: string; k?: number }) =>
    request<KnowledgeSearchResponse>("/knowledge/search", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  chat: (payload: ChatRequest) =>
    request<ChatResponse>("/agent/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  transcribeAudio: async (file: File): Promise<TranscriptionApiResult> => {
    const normalizedAudioType = file.type.toLowerCase().split(";", 1)[0].trim() || file.type;
    const normalizedAudioFile =
      normalizedAudioType && normalizedAudioType !== file.type
        ? new File([file], file.name, { type: normalizedAudioType, lastModified: file.lastModified })
        : file;
    const formData = new FormData();
    formData.append("file", normalizedAudioFile);
    formData.append("frontend_created_filename", normalizedAudioFile.name);
    const clientRequestId =
      typeof globalThis.crypto !== "undefined" && "randomUUID" in globalThis.crypto
        ? globalThis.crypto.randomUUID()
        : `req_${Date.now().toString(36)}`;
    const requestUrl = `${API_URL}/speech/transcribe`;
    const t0 = Date.now();
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[speech] transcribe request", {
        clientRequestId,
        requestUrl,
        createdFileName: normalizedAudioFile.name,
        createdFileType: normalizedAudioFile.type,
        fileSizeBytes: normalizedAudioFile.size,
      });
    }
    const response = await fetch(requestUrl, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Request-Id": clientRequestId,
      },
    });
    const elapsedMs = Date.now() - t0;
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[speech] transcribe response meta", {
        clientRequestId,
        responseStatus: response.status,
        elapsedMs,
      });
    }
    if (!response.ok) {
      let detail: unknown;
      try {
        const body = (await response.json()) as { detail?: unknown };
        detail = body.detail;
      } catch {
        detail = undefined;
      }
      throw new ApiError(
        formatErrorDetail(detail) ?? `Request failed: ${response.status}`,
        response.status,
        detail,
      );
    }
    const raw = (await response.json()) as Record<string, unknown>;
    const transcript = typeof raw.transcript === "string"
      ? raw.transcript
      : typeof raw.text === "string"
        ? raw.text
        : "";
    const normalized: TranscriptionResult = {
      request_id: typeof raw.request_id === "string" ? raw.request_id : null,
      transcript,
      detected_language: typeof raw.detected_language === "string" ? raw.detected_language : null,
      response_language: typeof raw.response_language === "string"
        ? raw.response_language
        : typeof raw.language === "string"
          ? raw.language
          : null,
      provider_mode: normalizeSpeechProviderMode(raw.provider_mode ?? raw.provider),
      confidence: typeof raw.confidence === "number" ? raw.confidence : null,
      fallback_reason: typeof raw.fallback_reason === "string" ? raw.fallback_reason : null,
      demo_transcript: typeof raw.demo_transcript === "string" ? raw.demo_transcript : null,
      message: typeof raw.message === "string" ? raw.message : null,
      fallback_used: typeof raw.fallback_used === "boolean" ? raw.fallback_used : null,
      openai_called: typeof raw.openai_called === "boolean" ? raw.openai_called : null,
      openai_response_received:
        typeof raw.openai_response_received === "boolean" ? raw.openai_response_received : null,
    };
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[speech] transcribe payload", {
        clientRequestId,
        serverRequestId: normalized.request_id,
        responseStatus: response.status,
        providerMode: normalized.provider_mode,
        fallbackUsed: normalized.fallback_used,
        openaiCalled: normalized.openai_called,
        openaiResponseReceived: normalized.openai_response_received,
        transcriptPreview: normalized.transcript.slice(0, 160),
        demoTranscript: normalized.demo_transcript,
        message: normalized.message,
      });
    }
    return { result: normalized, httpStatus: response.status, clientRequestId };
  },
  transcribeSpeech: async (file: File): Promise<TranscriptionApiResult> => api.transcribeAudio(file),
  speechCapabilities: (): Promise<SpeechCapabilities> => request<SpeechCapabilities>("/speech/capabilities"),
};

export { ApiError };
