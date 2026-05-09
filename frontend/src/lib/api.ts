import type {
  Approval,
  ApprovalDecisionPayload,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  FeedbackCreate,
  RecentFeedbackItem,
  FeedbackResponse,
  FeedbackSummary,
  HealthStatus,
  KnowledgeDocument,
  Investigation,
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
  mockPortfolio,
  mockReports,
  mockReportSummary,
  mockScenarioSummary,
  mockScenarios,
  mockUsageEvents,
  mockUsageSummary,
} from "@/lib/mock";
import { stripUndefinedDeep } from "@/lib/reportMemoPayload";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";
const DEFAULT_TIMEOUT_MS = 8000;
const CHAT_TIMEOUT_MS = 45000;

function normalizeSpeechProviderMode(raw: unknown): NonNullable<TranscriptionResult["provider_mode"]> {
  if (raw === "real" || raw === "openai") return "real";
  return "fallback";
}

export type TranscriptionApiResult = {
  result: TranscriptionResult;
  httpStatus: number;
  clientRequestId: string;
};

export type ChatApiResult = {
  result: ChatResponse;
  httpStatus: number;
  clientRequestId: string;
};

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
    /** Client-generated id (e.g. memo/report POST) when backend omits it in the body. */
    public clientRequestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function formatErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const rec = item as Record<string, unknown>;
        const loc = Array.isArray(rec.loc) ? (rec.loc as unknown[]).join(".") : "";
        const msg = typeof rec.msg === "string" ? rec.msg : String(rec.msg ?? "");
        return loc ? `${loc}: ${msg}` : msg;
      }
      return JSON.stringify(item);
    });
    return parts.join("; ");
  }
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const apiCode = typeof record.code === "string" ? record.code : null;
    const apiMessage = typeof record.message === "string" ? record.message : null;
    if (apiCode && apiMessage?.trim()) {
      return `${apiCode} — ${apiMessage}`;
    }
    if (apiMessage?.trim() && !apiCode) {
      return apiMessage;
    }
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

function extractRequestIdFromDetail(detail: unknown): string | null {
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const rid = (detail as Record<string, unknown>).request_id;
    if (typeof rid === "string" && rid.trim()) return rid;
  }
  return null;
}

/** User-visible message for report / memo API failures (no stack traces). */
export function formatMemoReportError(error: unknown): string {
  if (error instanceof ApiError) {
    const detailText = formatErrorDetail(error.detail) ?? error.message;
    const requestId =
      extractRequestIdFromDetail(error.detail) ?? error.clientRequestId ?? null;
    const ridSuffix = requestId ? ` Request id: ${requestId}.` : "";
    if (error.status === 401) {
      return `Memo generation failed: 401 — ${detailText}. Please sign in again.${ridSuffix}`;
    }
    if (error.status === 403) {
      return `Memo generation failed: 403 — ${detailText}.${ridSuffix}`;
    }
    if (error.status === 422) {
      return `Memo generation failed: 422 invalid report payload — ${detailText}${ridSuffix}`.trim();
    }
    if (error.status >= 500) {
      const rec =
        error.detail && typeof error.detail === "object" && !Array.isArray(error.detail)
          ? (error.detail as Record<string, unknown>)
          : null;
      const backendCode = typeof rec?.code === "string" ? rec.code : null;
      const backendMsg =
        typeof rec?.message === "string" ? rec.message : null;
      const vague =
        /^Request failed:\s*\d+$/.test(detailText.trim()) ||
        (backendCode === "internal_error" &&
          (backendMsg === "An unexpected error occurred." ||
            detailText === "internal_error — An unexpected error occurred."));
      if (vague) {
        return `Report service crashed. Check backend logs with request id: ${requestId ?? "n/a"}.`;
      }
      const line =
        backendCode && backendMsg
          ? `${error.status} ${backendCode} — ${backendMsg}`
          : `${error.status} — ${detailText}`;
      return `Memo generation failed: ${line}.${ridSuffix}`.trim();
    }
    return `Memo generation failed (${error.status}): ${detailText}${ridSuffix}`.trim();
  }
  if (error instanceof Error && error.name === "AbortError") {
    return "Memo generation failed: request timed out or was cancelled.";
  }
  return "Memo generation failed: unexpected error.";
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
        const body = (await response.json()) as Record<string, unknown>;
        detail = "detail" in body && body.detail !== undefined ? body.detail : body;
      } catch {
        detail = undefined;
      }
      const message =
        formatErrorDetail(detail) ?? `Request failed: ${response.status}`;
      throw new ApiError(message, response.status, detail);
    }
    if (process.env.NODE_ENV === "development" && path.startsWith("/approvals")) {
      // eslint-disable-next-line no-console
      console.debug("[approvals] request success", {
        route: path,
        method: init.method ?? "GET",
        response_status: response.status,
      });
    }
    if (response.status === 204) {
      return undefined as T;
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
  return request<Approval[]>("/approvals");
}

async function listApprovals(status?: Approval["status"]): Promise<Approval[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<Approval[]>(`/approvals${query}`);
}

async function decideApproval(
  approvalId: string,
  payload: ApprovalDecisionPayload,
): Promise<Approval> {
  if (process.env.NODE_ENV === "development") {
    // eslint-disable-next-line no-console
    console.debug("[approvals] decision request", {
      approval_id: approvalId,
      action: payload.status,
      route: `/approvals/${approvalId}/decision`,
    });
  }
  return request<Approval>(`/approvals/${approvalId}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function approveApproval(approvalId: string): Promise<Approval> {
  return decideApproval(approvalId, { status: "approved" });
}

async function rejectApproval(approvalId: string): Promise<Approval> {
  return decideApproval(approvalId, { status: "rejected" });
}

async function requestMoreAnalysis(approvalId: string): Promise<Approval> {
  return decideApproval(approvalId, { status: "needs_more_analysis" });
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
  listApprovals,
  fetchApprovals,
  decideApproval,
  approveApproval,
  rejectApproval,
  requestMoreAnalysis,
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
  createReport: async (payload: ReportCreate) => {
    const requestId =
      typeof globalThis.crypto !== "undefined" && "randomUUID" in globalThis.crypto
        ? globalThis.crypto.randomUUID()
        : `req_${Date.now().toString(36)}`;
    const body = JSON.stringify(stripUndefinedDeep(payload) as ReportCreate);
    try {
      return await request<ReportResponse>("/reports", {
        method: "POST",
        body,
        headers: { "X-Request-Id": requestId },
      });
    } catch (err) {
      if (err instanceof ApiError) {
        throw new ApiError(err.message, err.status, err.detail, requestId);
      }
      throw err;
    }
  },
  fetchReports: () => withFallback(request<ReportResponse[]>("/reports"), mockReports),
  fetchInvestigations: () => request<Investigation[]>("/investigations"),
  fetchInvestigation: (investigationId: string) =>
    request<Investigation>(`/investigations/${encodeURIComponent(investigationId)}`),
  deleteInvestigation: (investigationId: string) =>
    request<unknown>(`/investigations/${encodeURIComponent(investigationId)}`, {
      method: "DELETE",
    }),
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
  chat: async (
    payload: ChatRequest,
    options?: { clientRequestId?: string },
  ): Promise<ChatApiResult> => {
    const clientRequestId =
      options?.clientRequestId ??
      (typeof globalThis.crypto !== "undefined" && "randomUUID" in globalThis.crypto
        ? globalThis.crypto.randomUUID()
        : `req_${Date.now().toString(36)}`);
    const response = await fetch(`${API_URL}/agent/chat`, {
      method: "POST",
      body: JSON.stringify(payload),
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-Id": clientRequestId,
      },
      cache: "no-store",
      signal: AbortSignal.timeout(CHAT_TIMEOUT_MS),
    });
    if (!response.ok) {
      let detail: unknown;
      try {
        const body = (await response.json()) as Record<string, unknown>;
        detail = "detail" in body && body.detail !== undefined ? body.detail : body;
      } catch {
        detail = undefined;
      }
      const message = formatErrorDetail(detail) ?? `Request failed: ${response.status}`;
      throw new ApiError(message, response.status, detail, clientRequestId);
    }
    return {
      result: (await response.json()) as ChatResponse,
      httpStatus: response.status,
      clientRequestId,
    };
  },
  createConversation: (payload?: { title?: string | null }) =>
    request<ConversationSummary>("/conversations", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    }),
  listConversations: (limit = 20) =>
    request<ConversationSummary[]>(`/conversations?limit=${encodeURIComponent(String(limit))}`),
  getConversation: (conversationId: string) =>
    request<ConversationDetail>(`/conversations/${encodeURIComponent(conversationId)}`),
  deleteConversation: (conversationId: string) =>
    request<unknown>(`/conversations/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
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
