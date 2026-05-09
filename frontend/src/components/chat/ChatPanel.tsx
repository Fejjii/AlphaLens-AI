"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useCallback } from "react";
import type { MutableRefObject, ReactNode } from "react";
import {
  Circle,
  ExternalLink,
  Info,
  Loader2,
  Mic,
  Send,
  Sparkles,
  StopCircle,
  Upload,
  Volume2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorBanner } from "@/components/ui/error-banner";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ApprovalModeBadge,
  ConfidenceBadge,
  RecommendationBadge,
  RiskBadge,
} from "@/components/ui/status-badges";
import { emitPlanUsageChanged } from "@/lib/app-events";
import { ApiError, api, formatMemoReportError } from "@/lib/api";
import { buildInvestmentMemoReportPayload } from "@/lib/reportMemoPayload";
import { cn } from "@/lib/utils";
import type {
  AgentDecision,
  ChatAnswerType,
  ChatMessage,
  ChatRouting,
  Citation,
  ChatResponse,
  ConversationSummary,
  FeedbackCategory,
  FeedbackRating,
  SpeechCapabilities,
  TranscriptionResult,
} from "@/types/api";

interface ChatTurn {
  id: string;
  message: ChatMessage;
  citations?: Citation[];
  decision?: AgentDecision | null;
  responseId?: string | null;
  usedTools?: string[];
  analysis?: ChatResponse["analysis"];
  /** Present for assistant turns; drives investment vs simple card. */
  answerType?: ChatAnswerType;
  routing?: ChatRouting;
  investigationId?: string | null;
}

const SEED: ChatTurn[] = [
  {
    id: "seed",
    message: {
      role: "assistant",
      content:
        "Hello — I'm AlphaLens. Ask about portfolio performance, risk, research notes, or pending approvals.",
    },
  },
];

const DEFAULT_SPEECH_CAPABILITIES: SpeechCapabilities = {
  supported_mime_types: [
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
  ],
  max_upload_mb: 25,
  supported_languages: ["en", "de", "fr", "ar"],
  provider_mode: "fallback",
  openai_key_configured: false,
  microphone_transcription_available: false,
  message: "Speech capabilities not loaded yet.",
};

const MIME_TYPE_ALIASES: Record<string, string> = {
  "audio/x-wav": "audio/wav",
  "audio/mp3": "audio/mpeg",
  "audio/x-m4a": "audio/mp4",
};

const RECORDER_MIME_PREFERENCE = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
  "audio/mp4",
];
const DEMO_TRANSCRIPT = "Which policy rules are currently breached by the portfolio?";
const SPEECH_UNAVAILABLE_USER_MESSAGE =
  "Real speech transcription is not configured. Add OPENAI_API_KEY to transcribe your voice.";

function appendOnceToPrompt(current: string, addition: string): string {
  const t = current.trimEnd();
  const a = addition.trim();
  if (!t) return a;
  if (t === a || t.endsWith(a)) return t;
  return `${t} ${a}`;
}

const AVAILABLE_TOOLS = [
  { label: "Portfolio", description: "holdings, NAV, weights, P&L, cash, watchlist" },
  { label: "Policy", description: "structured investment rules and thresholds" },
  { label: "Market", description: "market prices and return data" },
  { label: "News", description: "web and news provider" },
  { label: "Macro", description: "FRED or macro fallback" },
  { label: "SEC", description: "EDGAR filings or fallback" },
  { label: "RAG", description: "internal vector knowledge base retrieval" },
] as const;

function normalizeAnswerType(raw: unknown): ChatAnswerType | undefined {
  if (
    raw === "app_help" ||
    raw === "out_of_scope" ||
    raw === "investment_decision" ||
    raw === "clarification"
  ) {
    return raw;
  }
  return undefined;
}

function conversationMessagesToTurns(messages: ChatMessage[], convId: string): ChatTurn[] {
  return messages.map((message, idx) => {
    if (message.role === "user") {
      return {
        id: `h_${convId}_u_${idx}`,
        message: { role: "user", content: message.content },
      };
    }
    const metadata = (message.metadata ?? {}) as Record<string, unknown>;
    const analysisCandidate = metadata.analysis;
    const decisionCandidate = metadata.decision;
    const citationsCandidate = metadata.citations;
    const toolsCandidate = metadata.tools_used;
    const routingCandidate = metadata.routing;
    const investigationCandidate = metadata.investigation_id;
    const routing =
      routingCandidate && typeof routingCandidate === "object"
        ? (routingCandidate as ChatRouting)
        : undefined;
    const intentRaw = typeof metadata.intent === "string" ? metadata.intent : "";
    const answerTypeRaw = normalizeAnswerType(
      (routing?.answer_type as string | undefined) ?? metadata.answer_type,
    );
    const prev = idx > 0 ? messages[idx - 1] : null;
    const prevUserContent = prev?.role === "user" ? prev.content : "";
    const userHintsInvestment =
      /\b(portfolio|holding|holdings|nav|pnl|mandate|breach|rag|knowledge\s*base|nvda|msft|aapl|trim|rebalance|buy|sell|policy|10-?k|sec|filing)\b/i.test(
        prevUserContent,
      );
    let answerType: ChatAnswerType;
    if (intentRaw === "general_question") {
      answerType =
        answerTypeRaw != null && answerTypeRaw !== "investment_decision"
          ? answerTypeRaw
          : "app_help";
    } else if (answerTypeRaw != null) {
      answerType = answerTypeRaw;
    } else if (decisionCandidate && typeof decisionCandidate === "object") {
      answerType = userHintsInvestment ? "investment_decision" : "app_help";
    } else {
      answerType = "app_help";
    }
    return {
      id: `h_${convId}_a_${idx}`,
      message: { role: "assistant", content: message.content },
      analysis: (analysisCandidate ?? undefined) as ChatResponse["analysis"] | undefined,
      decision: (decisionCandidate ?? undefined) as AgentDecision | null | undefined,
      citations: Array.isArray(citationsCandidate) ? (citationsCandidate as Citation[]) : undefined,
      usedTools: Array.isArray(toolsCandidate) ? (toolsCandidate as string[]) : undefined,
      responseId: typeof metadata.response_id === "string" ? metadata.response_id : null,
      answerType,
      routing,
      investigationId:
        typeof investigationCandidate === "string" ? investigationCandidate : null,
    };
  });
}

function formatRelativeUpdated(iso: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const deltaSec = Math.round((Date.now() - t) / 1000);
  if (deltaSec < 60) return "just now";
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}m ago`;
  if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)}h ago`;
  if (deltaSec < 604800) return `${Math.floor(deltaSec / 86400)}d ago`;
  return new Date(t).toLocaleDateString();
}

export function ChatPanel() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [turns, setTurns] = useState<ChatTurn[]>(SEED);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [recentConversations, setRecentConversations] = useState<ConversationSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [transcribingSource, setTranscribingSource] = useState<"recording" | "upload" | null>(null);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [speechErrorIsQuota, setSpeechErrorIsQuota] = useState(false);
  const [speechSuccess, setSpeechSuccess] = useState<string | null>(null);
  const [speechNotice, setSpeechNotice] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [audioDialogOpen, setAudioDialogOpen] = useState(false);
  const [audioMode, setAudioMode] = useState<"recording" | "upload">("recording");
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [capabilities, setCapabilities] = useState<SpeechCapabilities>(DEFAULT_SPEECH_CAPABILITIES);
  const [microphoneUnavailable, setMicrophoneUnavailable] = useState(false);
  const [lastTranscriptionForDemo, setLastTranscriptionForDemo] = useState<TranscriptionResult | null>(null);
  const [speechDevPanel, setSpeechDevPanel] = useState<Record<string, string | boolean | number | null> | null>(
    null,
  );
  const [promptMergeOffer, setPromptMergeOffer] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const inputValueRef = useRef("");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordingIntervalRef = useRef<number | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingSessionRef = useRef({
    selectedMediaRecorderMimeType: null as string | null,
    mediaRecorderSupported: typeof MediaRecorder !== "undefined",
    recordingStartedAt: null as string | null,
    recordingStoppedAt: null as string | null,
    dataavailableEventCount: 0,
    chunkSizes: [] as number[],
    finalBlobType: null as string | null,
    finalBlobSize: null as number | null,
  });
  const lastInsertedSpeechKeyRef = useRef<string | null>(null);
  const transcriptionGenerationRef = useRef(0);
  const capabilitiesRef = useRef(capabilities);
  const isSendingRef = useRef(false);

  const refreshConversations = useCallback(async () => {
    try {
      const items = await api.listConversations(6);
      const seen = new Set<string>();
      const deduped: ConversationSummary[] = [];
      for (const item of items) {
        if (seen.has(item.conversation_id)) continue;
        seen.add(item.conversation_id);
        if (item.message_count > 0) deduped.push(item);
      }
      setRecentConversations(deduped);
    } catch {
      setRecentConversations([]);
    }
  }, []);

  const syncConversationInUrl = useCallback(
    (id: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("conversation_id", id);
      router.replace(`${pathname}?${params.toString()}`);
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    capabilitiesRef.current = capabilities;
  }, [capabilities]);

  useEffect(() => {
    inputValueRef.current = input;
  }, [input]);

  useEffect(() => {
    if (process.env.NODE_ENV !== "development") return;
    // eslint-disable-next-line no-console
    console.debug("[chat] state", {
      conversation_id: conversationId,
      message_count: turns.length,
      history_loaded: !historyLoading,
      route: `${pathname}?${searchParams.toString()}`,
      memory_backend: "backend",
    });
  }, [conversationId, historyLoading, pathname, searchParams, turns.length]);

  useEffect(() => {
    void api
      .speechCapabilities()
      .then((result) => setCapabilities(result))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    return () => {
      cleanupRecording(mediaRecorderRef, mediaStreamRef, recordingIntervalRef);
    };
  }, []);

  useEffect(() => {
    if (audioDialogOpen) {
      void api.speechCapabilities().then(setCapabilities).catch(() => undefined);
    }
  }, [audioDialogOpen]);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    const presetPrompt = searchParams.get("prompt");
    const mode = searchParams.get("mode");
    if (mode === "investigation" && presetPrompt && !inputValueRef.current.trim()) {
      setInput(presetPrompt);
    }
  }, [searchParams]);

  useEffect(() => {
    const id = searchParams.get("conversation_id");
    if (!id) {
      setHistoryLoading(false);
      setConversationId(null);
      setTurns(SEED);
      setHistoryError(null);
      return;
    }
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError(null);
    void api
      .getConversation(id)
      .then((conversation) => {
        if (cancelled) return;
        setConversationId(id);
        const loadedTurns =
          conversation.messages.length > 0
            ? conversationMessagesToTurns(conversation.messages, id)
            : SEED;
        setTurns(loadedTurns.length > 0 ? loadedTurns : SEED);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 404) {
          setRecentConversations((prev) => prev.filter((c) => c.conversation_id !== id));
          setHistoryError("This conversation no longer exists.");
        } else {
          setHistoryError("Unable to load conversation history.");
        }
        setConversationId(null);
        router.replace(pathname);
        setTurns(SEED);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [searchParams, pathname, router]);

  const refreshSpeechCapabilities = useCallback(() => {
    void api.speechCapabilities().then(setCapabilities).catch(() => undefined);
  }, []);

  const startNewChat = useCallback(() => {
    setConversationId(null);
    setTurns(SEED);
    setHistoryError(null);
    router.replace(pathname);
    void refreshConversations();
  }, [pathname, refreshConversations, router]);

  const loadConversation = useCallback(
    async (id: string) => {
      setHistoryLoading(true);
      setHistoryError(null);
      try {
        const conversation = await api.getConversation(id);
        const loadedTurns =
          conversation.messages.length > 0
            ? conversationMessagesToTurns(conversation.messages, id)
            : SEED;
        setConversationId(id);
        setTurns(loadedTurns.length > 0 ? loadedTurns : SEED);
        syncConversationInUrl(id);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          setRecentConversations((prev) => prev.filter((c) => c.conversation_id !== id));
          setHistoryError("This conversation no longer exists.");
        } else {
          setHistoryError("Unable to load selected conversation.");
        }
        setConversationId(null);
        router.replace(pathname);
        setTurns(SEED);
      } finally {
        setHistoryLoading(false);
      }
    },
    [pathname, router, syncConversationInUrl],
  );

  const deleteCurrentConversation = useCallback(async () => {
    if (!conversationId) return;
    try {
      await api.deleteConversation(conversationId);
      setRecentConversations((prev) => prev.filter((c) => c.conversation_id !== conversationId));
      setConversationId(null);
      setTurns(SEED);
      setHistoryError(null);
      router.replace(pathname);
      await refreshConversations();
    } catch {
      setHistoryError("Could not delete this conversation.");
    }
  }, [conversationId, pathname, refreshConversations, router]);

  const micTranscriptionAvailable = capabilities.microphone_transcription_available;
  const requestUrlLabel = `${process.env.NEXT_PUBLIC_API_URL ?? "/api/backend"}/speech/transcribe`;

  const applyTranscriptWithDedupe = useCallback((text: string, dedupeKey: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (lastInsertedSpeechKeyRef.current === dedupeKey) return;
    lastInsertedSpeechKeyRef.current = dedupeKey;
    setPromptMergeOffer(null);

    const el = inputRef.current;
    const cur = inputValueRef.current;
    const start = el?.selectionStart ?? null;
    const end = el?.selectionEnd ?? null;
    const hasFocus =
      el != null && typeof document !== "undefined" && document.activeElement === el;

    if (!cur.trim()) {
      setInput(trimmed);
      return;
    }
    if (hasFocus && start != null && end != null && start !== end) {
      setInput(cur.slice(0, start) + trimmed + cur.slice(end));
      return;
    }
    setPromptMergeOffer(trimmed);
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const content = input.trim();
    if (!content || pending || isSendingRef.current) return;

    isSendingRef.current = true;
    const clientMessageId =
      typeof globalThis.crypto !== "undefined" && "randomUUID" in globalThis.crypto
        ? globalThis.crypto.randomUUID()
        : `u_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

    const userTurn: ChatTurn = {
      id: `u_${clientMessageId}`,
      message: { role: "user", content },
    };
    setTurns((prev) => [...prev, userTurn]);
    setInput("");
    setPending(true);
    setChatError(null);

    try {
      const response = await api.chat({
        conversation_id: conversationId ?? undefined,
        messages: [userTurn.message],
      });
      const finalAnswer = response.analysis?.final_answer?.trim();
      const renderedContent = finalAnswer || response.message?.content?.trim() || "";
      if (!renderedContent) {
        setTurns((prev) => prev.filter((t) => t.id !== userTurn.id));
        setInput(content);
        setChatError(
          process.env.NODE_ENV === "development"
            ? "Malformed agent response: final_answer missing"
            : "Agent response is incomplete.",
        );
        return;
      }
      setConversationId(response.conversation_id);
      syncConversationInUrl(response.conversation_id);
      const answerType: ChatAnswerType = response.answer_type ?? "investment_decision";
      setTurns((prev) => [
        ...prev,
        {
          id: `a_${response.response_id ?? Date.now()}`,
          message: {
            ...response.message,
            content: renderedContent,
          },
          citations: response.citations,
          decision: response.decision ?? null,
          responseId: response.response_id,
          usedTools: response.used_tools,
          analysis: response.analysis,
          answerType,
          routing: response.routing,
          investigationId: response.investigation_id ?? null,
        },
      ]);
      void refreshConversations();
    } catch (error) {
      setTurns((prev) => prev.filter((t) => t.id !== userTurn.id));
      setInput(content);
      if (error instanceof ApiError && error.message.trim()) {
        setChatError(error.message);
      } else {
        setChatError("Chat request failed. Check backend and retry.");
      }
    } finally {
      isSendingRef.current = false;
      setPending(false);
    }
  };

  const handleTranscription = async (file: File, source: "recording" | "upload") => {
    if (pending || transcribing) return;

    setSpeechError(null);
    setSpeechErrorIsQuota(false);
    setSpeechSuccess(null);
    setSpeechNotice(null);
    setTranscribing(true);
    setTranscribingSource(source);
    const gen = ++transcriptionGenerationRef.current;

    const recordingStartedAt = recordingSessionRef.current.recordingStartedAt;
    const recordingStoppedAt = recordingSessionRef.current.recordingStoppedAt;
    const dataavailableEventCount = recordingSessionRef.current.dataavailableEventCount;
    const chunkSizes = [...recordingSessionRef.current.chunkSizes];
    const selectedMime = recordingSessionRef.current.selectedMediaRecorderMimeType;
    const mediaRecorderSupported = recordingSessionRef.current.mediaRecorderSupported;

    try {
      const { result, httpStatus, clientRequestId } = await api.transcribeAudio(file);
      if (gen !== transcriptionGenerationRef.current) return;

      const insertKey = result.request_id
        ? `rid:${result.request_id}`
        : `cid:${clientRequestId}`;
      const trimmed = result.transcript.trim();
      const isFallback = result.provider_mode === "fallback" || result.fallback_used === true;

      if (process.env.NODE_ENV === "development") {
        const rec = selectedMime ?? null;
        // eslint-disable-next-line no-console
        console.debug("[speech] e2e trace", {
          selected_media_recorder_mime_type: rec,
          media_recorder_supported: mediaRecorderSupported,
          recording_started_at: source === "recording" ? recordingStartedAt : null,
          recording_stopped_at: source === "recording" ? recordingStoppedAt : null,
          dataavailable_event_count: source === "recording" ? dataavailableEventCount : null,
          chunk_sizes: source === "recording" ? chunkSizes : null,
          final_blob_type: source === "recording" ? recordingSessionRef.current.finalBlobType : file.type,
          final_blob_size: source === "recording" ? recordingSessionRef.current.finalBlobSize : file.size,
          created_file_name: file.name,
          created_file_type: file.type,
          request_url: requestUrlLabel,
          response_status: httpStatus,
          response_provider_mode: result.provider_mode,
          response_transcript: result.transcript,
          response_demo_transcript: result.demo_transcript ?? null,
          openai_called: result.openai_called,
          fallback_used: result.fallback_used,
          insert_reason: "pending",
        });
      }

      setSpeechDevPanel(
        process.env.NODE_ENV === "development"
          ? {
              capabilities_provider_mode: capabilitiesRef.current.provider_mode,
              capabilities_openai_key_configured: capabilitiesRef.current.openai_key_configured,
              selected_recorder_mime: selectedMime ?? "",
              final_blob_size: source === "recording" ? (recordingSessionRef.current.finalBlobSize ?? 0) : file.size,
              response_status: httpStatus,
              response_provider_mode: result.provider_mode ?? "",
              openai_called: result.openai_called ?? false,
              fallback_used: result.fallback_used ?? false,
              transcript_preview: (result.transcript || "").slice(0, 120),
              demo_transcript: (result.demo_transcript || "").slice(0, 120),
            }
          : null,
      );

      if (isFallback) {
        setLastTranscriptionForDemo(result);
        setSpeechNotice(result.message ?? SPEECH_UNAVAILABLE_USER_MESSAGE);
        setSpeechError(null);
        setSpeechErrorIsQuota(false);
        setSpeechSuccess(null);
        return;
      }

      if (!trimmed) {
        setLastTranscriptionForDemo(null);
        setSpeechError("Transcription returned no text. Try again or check backend speech logs.");
        setSpeechSuccess(null);
        setSpeechNotice(null);
        if (process.env.NODE_ENV === "development") {
          setSpeechDevPanel((prev) =>
            prev
              ? { ...prev, inserted_into_prompt: "false", insert_reason: "empty_transcript" }
              : prev,
          );
        }
        return;
      }

      setLastTranscriptionForDemo(null);
      setSpeechNotice(null);
      applyTranscriptWithDedupe(trimmed, insertKey);
      setSpeechSuccess("Transcription ready.");
      setAudioDialogOpen(false);
      if (process.env.NODE_ENV === "development") {
        setSpeechDevPanel((prev) =>
          prev
            ? { ...prev, inserted_into_prompt: "true", insert_reason: "real_transcript" }
            : prev,
        );
      }
    } catch (error) {
      if (gen !== transcriptionGenerationRef.current) return;
      setLastTranscriptionForDemo(null);
      setSpeechNotice(null);
      if (error instanceof ApiError) {
        setSpeechErrorIsQuota(isQuotaExceededDetail(error.detail));
        setSpeechError(formatSpeechError(error));
      } else {
        setSpeechErrorIsQuota(false);
        setSpeechError("Transcription failed. Please retry with another recording or file.");
      }
    } finally {
      emitPlanUsageChanged();
      if (gen === transcriptionGenerationRef.current) {
        setTranscribing(false);
        setTranscribingSource(null);
      }
    }
  };

  const handleAudioUpload = async (file: File) => {
    if (!micTranscriptionAvailable) {
      setSpeechError(SPEECH_UNAVAILABLE_USER_MESSAGE);
      return;
    }
    const maxUploadBytes = capabilities.max_upload_mb * 1024 * 1024;
    if (file.size > maxUploadBytes) {
      setSpeechError(`Audio exceeds ${capabilities.max_upload_mb} MB. Please choose a smaller file.`);
      return;
    }
    if (!isMimeTypeSupported(file.type, capabilities.supported_mime_types)) {
      setSpeechError("Unsupported audio format. Please select one of the listed formats.");
      return;
    }
    await handleTranscription(file, "upload");
  };

  const startRecording = async () => {
    if (pending || transcribing || isRecording) return;
    if (typeof window === "undefined" || typeof navigator === "undefined") {
      setSpeechError("Live microphone recording is not available in this environment.");
      setMicrophoneUnavailable(true);
      setAudioMode("upload");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setSpeechError("Microphone recording is unavailable in this browser. Use upload mode instead.");
      setMicrophoneUnavailable(true);
      setAudioMode("upload");
      return;
    }
    if (typeof MediaRecorder === "undefined") {
      setSpeechError("Microphone recording is unavailable in this browser. Use upload mode instead.");
      setMicrophoneUnavailable(true);
      setAudioMode("upload");
      return;
    }
    if (!capabilitiesRef.current.microphone_transcription_available) {
      setSpeechError(SPEECH_UNAVAILABLE_USER_MESSAGE);
      return;
    }

    recordingSessionRef.current = {
      selectedMediaRecorderMimeType: null,
      mediaRecorderSupported: typeof MediaRecorder !== "undefined",
      recordingStartedAt: null,
      recordingStoppedAt: null,
      dataavailableEventCount: 0,
      chunkSizes: [],
      finalBlobType: null,
      finalBlobSize: null,
    };

    setSpeechError(null);
    setSpeechSuccess(null);
    setMicrophoneUnavailable(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferredMimeType = pickRecorderMimeType();
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.debug("[speech] selected recorder mime", { preferredMimeType });
      }
      const recorder = preferredMimeType
        ? new MediaRecorder(stream, { mimeType: preferredMimeType })
        : new MediaRecorder(stream);

      recordingSessionRef.current.selectedMediaRecorderMimeType =
        preferredMimeType ?? (recorder.mimeType || null);

      mediaStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (event: BlobEvent) => {
        recordingSessionRef.current.dataavailableEventCount += 1;
        if (process.env.NODE_ENV === "development") {
          // eslint-disable-next-line no-console
          console.debug("[speech] dataavailable", { size: event.data.size });
        }
        if (event.data.size > 0) {
          recordingSessionRef.current.chunkSizes.push(event.data.size);
          audioChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        const blobType = recorder.mimeType || preferredMimeType || "audio/webm";
        const normalizedBlobType = normalizeAudioMimeType(blobType);
        const audioBlob = new Blob(audioChunksRef.current, { type: blobType });
        recordingSessionRef.current.recordingStoppedAt = new Date().toISOString();
        recordingSessionRef.current.finalBlobType = normalizedBlobType;
        recordingSessionRef.current.finalBlobSize = audioBlob.size;
        cleanupRecording(mediaRecorderRef, mediaStreamRef, recordingIntervalRef);
        setIsRecording(false);
        if (process.env.NODE_ENV === "development") {
          // eslint-disable-next-line no-console
          console.debug("[speech] stop", {
            recorderState: recorder.state,
            chunksCount: recordingSessionRef.current.chunkSizes.length,
            blobSize: audioBlob.size,
          });
        }
        if (audioBlob.size === 0) {
          setSpeechError("Recording was empty. Please try speaking before stopping.");
          return;
        }
        const filename = `recording.${extensionFromMimeType(normalizedBlobType)}`;
        if (process.env.NODE_ENV === "development") {
          // eslint-disable-next-line no-console
          console.debug("[speech] microphone blob", {
            mimeType: normalizedBlobType,
            size: audioBlob.size,
            filename,
          });
        }
        if (!capabilitiesRef.current.microphone_transcription_available) {
          setSpeechError(SPEECH_UNAVAILABLE_USER_MESSAGE);
          return;
        }
        const file = new File([audioBlob], filename, { type: normalizedBlobType });
        void handleTranscription(file, "recording");
      };

      recorder.start(300);
      recordingSessionRef.current.recordingStartedAt = new Date().toISOString();
      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.debug("[speech] recording started", { recorderState: recorder.state });
      }
      setIsRecording(true);
      setRecordingSeconds(0);
      recordingIntervalRef.current = window.setInterval(() => {
        setRecordingSeconds((current) => current + 1);
      }, 1000);
    } catch (error) {
      setSpeechError(getMicrophoneErrorMessage(error));
      setMicrophoneUnavailable(true);
      setAudioMode("upload");
      cleanupRecording(mediaRecorderRef, mediaStreamRef, recordingIntervalRef);
      setIsRecording(false);
    }
  };

  const stopRecording = () => {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== "recording") {
      return;
    }
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.debug("[speech] stop requested");
    }
    mediaRecorderRef.current.requestData();
    mediaRecorderRef.current.stop();
  };

  const closeAudioDialog = () => {
    if (isRecording) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.onstop = null;
        mediaRecorderRef.current.stop();
      }
      cleanupRecording(mediaRecorderRef, mediaStreamRef, recordingIntervalRef);
      setIsRecording(false);
      setRecordingSeconds(0);
    }
    setAudioDialogOpen(false);
  };

  return (
    <Card className="flex h-[calc(100vh-8.25rem)] flex-col overflow-hidden">
      <CardContent className="flex flex-1 min-h-0 flex-col gap-4 p-0">
        <div className="border-b border-border/70 px-5 py-4 md:px-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="section-label">Conversation workspace</div>
              <div className="mt-2 text-lg font-semibold tracking-tight">Agent chat</div>
              <p className="mt-1 text-sm text-muted-foreground">
                Investigate portfolio, policy, market, news, macro, SEC, and retrieval context in one thread.
              </p>
            </div>
            <div className="max-w-xl">
              <div className="mb-2 flex justify-end gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => void startNewChat()}>
                  New chat
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={!conversationId}
                  onClick={() => void deleteCurrentConversation()}
                >
                  Delete
                </Button>
              </div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Available tools
              </div>
              <div className="flex flex-wrap gap-2">
                {AVAILABLE_TOOLS.map((tool) => (
                  <Badge key={tool.label} variant="outline" title={tool.description} className="cursor-help">
                    {tool.label}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </div>

        <ScrollArea className="flex-1 px-4 md:px-6">
          <div className="space-y-4 py-5">
            {historyLoading && (
              <div className="max-w-2xl rounded-[0.875rem] border border-border/60 bg-card/60 px-4 py-3 text-sm text-muted-foreground">
                Loading conversation history...
              </div>
            )}
            <div className="max-w-2xl rounded-[0.875rem] border border-border/60 bg-card/60 px-4 py-3">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Recent chats
              </div>
              {recentConversations.length === 0 ? (
                <p className="text-xs text-muted-foreground">No previous chats yet.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {recentConversations.map((conversation) => {
                    const label =
                      conversation.title.length > 48
                        ? `${conversation.title.slice(0, 48)}…`
                        : conversation.title;
                    const rel = formatRelativeUpdated(conversation.updated_at);
                    return (
                      <Button
                        key={conversation.conversation_id}
                        type="button"
                        size="sm"
                        variant={conversation.conversation_id === conversationId ? "default" : "outline"}
                        className="h-auto max-w-[14rem] shrink-0 rounded-lg px-2.5 py-1.5 text-left font-normal"
                        title={`${conversation.title}${rel ? ` · ${rel}` : ""}`}
                        onClick={() => void loadConversation(conversation.conversation_id)}
                      >
                        <span className="line-clamp-2 break-words text-xs leading-snug">{label}</span>
                        {rel ? (
                          <span className="mt-0.5 block text-[10px] text-muted-foreground">{rel}</span>
                        ) : null}
                      </Button>
                    );
                  })}
                </div>
              )}
            </div>
            {historyError && (
              <ErrorBanner title="Conversation history issue" message={historyError} className="max-w-2xl" />
            )}
            {chatError && (
              <ErrorBanner
                title="Agent chat failed"
                message={chatError}
                className="max-w-2xl"
              />
            )}
            {turns.map((turn) => (
              <ChatBubble key={turn.id} turn={turn} conversationId={conversationId} />
            ))}
            {pending && (
              <ThinkingState />
            )}
            {transcribing && (
              <div className="rounded-[1rem] border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-primary">
                <div className="flex items-center gap-2 font-medium">
                  <Volume2 className="h-4 w-4" />
                  {transcribingSource === "recording" ? "Transcribing microphone recording" : "Transcribing audio"}
                </div>
                <p className="mt-1 text-primary/80">
                  AlphaLens is extracting the question so you can review it before sending.
                </p>
              </div>
            )}
            {speechError && (
              <ErrorBanner
                title={speechErrorIsQuota ? "Speech limit reached" : "Audio transcription failed"}
                message={speechError}
                actionLabel={speechErrorIsQuota ? "View usage" : "Retry"}
                onAction={() =>
                  speechErrorIsQuota ? (window.location.href = "/usage") : setAudioDialogOpen(true)
                }
                className="max-w-2xl"
              />
            )}
            {speechSuccess && (
              <div className="max-w-2xl rounded-[0.875rem] border border-emerald-500/25 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                {speechSuccess}
              </div>
            )}
            {speechNotice && (
              <div className="max-w-2xl rounded-[0.875rem] border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100">
                {speechNotice}
                <div className="mt-2 text-xs text-muted-foreground">
                  Use &quot;Insert demo transcript&quot; in the Audio window only if you intend to load the sample
                  prompt.
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
        <div className="border-t border-border/70 px-4 py-4 md:px-6">
          <form onSubmit={handleSubmit} className="rounded-[1rem] border border-border/70 bg-background/75 p-3">
            <input
              ref={fileInputRef}
              type="file"
              accept={buildAcceptList(capabilities.supported_mime_types)}
              className="hidden"
              disabled={pending || transcribing || !micTranscriptionAvailable}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  void handleAudioUpload(file);
                }
                event.target.value = "";
              }}
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="section-label">Prompt</span>
                  <span className="text-xs text-muted-foreground">
                    {pending
                      ? "Waiting for response..."
                      : isRecording
                        ? `Recording ${formatDuration(recordingSeconds)}`
                        : transcribing
                          ? "Transcription in progress..."
                          : "Ready"}
                  </span>
                </div>
                <Input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about portfolio, risk, research notes, or pending approvals..."
                  disabled={pending || transcribing}
                />
              </div>
              {promptMergeOffer ? (
                <div className="mt-2 flex flex-wrap items-center gap-2 rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-2">
                  <span className="text-xs text-muted-foreground">New transcript ready — replace the prompt or append once.</span>
                  <Button
                    type="button"
                    size="sm"
                    variant="default"
                    disabled={pending || transcribing}
                    onClick={() => {
                      setInput(promptMergeOffer);
                      setPromptMergeOffer(null);
                    }}
                  >
                    Replace prompt
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={pending || transcribing}
                    onClick={() => {
                      setInput((c) => appendOnceToPrompt(c, promptMergeOffer));
                      setPromptMergeOffer(null);
                    }}
                  >
                    Append once
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={pending || transcribing}
                    onClick={() => setPromptMergeOffer(null)}
                  >
                    Dismiss
                  </Button>
                </div>
              ) : null}
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={pending || transcribing}
                  onClick={() => {
                    refreshSpeechCapabilities();
                    setAudioDialogOpen(true);
                  }}
                  aria-label="Upload audio"
                >
                  {transcribing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mic className="h-4 w-4" />}
                  Audio
                </Button>
                <Button type="submit" disabled={pending || transcribing || !input.trim()}>
                  {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Send
                </Button>
              </div>
            </div>
          </form>
        </div>
      </CardContent>
      {audioDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[1rem] border border-border/70 bg-card p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-semibold">Audio input</div>
                <div className="text-xs text-muted-foreground">
                  Record from your microphone or upload an audio file.
                </div>
              </div>
              <Button size="sm" variant="ghost" onClick={closeAudioDialog}>
                Close
              </Button>
            </div>

            <div className="mb-3 flex gap-2">
              <Button
                type="button"
                size="sm"
                variant={audioMode === "recording" ? "default" : "outline"}
                disabled={transcribing}
                onClick={() => setAudioMode("recording")}
              >
                <Mic className="h-3.5 w-3.5" />
                Microphone
              </Button>
              <Button
                type="button"
                size="sm"
                variant={audioMode === "upload" ? "default" : "outline"}
                disabled={transcribing}
                onClick={() => setAudioMode("upload")}
              >
                <Upload className="h-3.5 w-3.5" />
                Upload
              </Button>
            </div>

            <div className="mb-3 rounded-[0.875rem] border border-border/50 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              {micTranscriptionAvailable ? (
                <span className="text-emerald-700 dark:text-emerald-300">
                  Voice transcription is available (OpenAI key configured on backend).
                </span>
              ) : (
                <span>{capabilities.message}</span>
              )}
            </div>

            {!micTranscriptionAvailable && (
              <div className="mb-3 space-y-2 rounded-[0.875rem] border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
                <div>
                  {lastTranscriptionForDemo?.demo_transcript
                    ? "The server returned a sample line you can insert manually (your recording was not transcribed with OpenAI)."
                    : "Insert the standard sample prompt for offline demos."}{" "}
                  Microphone and file upload stay disabled until the backend reports an OpenAI key.
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="w-full"
                  onClick={() => {
                    const demoText = lastTranscriptionForDemo?.demo_transcript ?? DEMO_TRANSCRIPT;
                    applyTranscriptWithDedupe(demoText, `demo:${Date.now()}`);
                    setSpeechSuccess("Demo transcript inserted.");
                    setSpeechNotice(null);
                    setAudioDialogOpen(false);
                    setLastTranscriptionForDemo(null);
                  }}
                >
                  Insert demo transcript
                </Button>
              </div>
            )}
            {audioMode === "recording" ? (
              <div className="space-y-3 rounded-[0.875rem] border border-border/60 bg-background/40 p-3">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">Live microphone</div>
                  <div className="font-mono text-xs text-muted-foreground">{formatDuration(recordingSeconds)}</div>
                </div>
                <p className="text-xs text-muted-foreground">
                  {micTranscriptionAvailable
                    ? "Click record, speak your prompt, then stop to transcribe and review before sending."
                    : "Recording is disabled until OPENAI_API_KEY is configured. Use Insert demo transcript or add a key and refresh."}
                </p>
                {microphoneUnavailable ? (
                  <div className="rounded-[0.75rem] border border-amber-500/30 bg-amber-500/10 px-2.5 py-2 text-xs text-amber-200">
                    Microphone recording is unavailable in this browser. Switch to upload mode or insert the demo
                    transcript.
                  </div>
                ) : null}
                <Button
                  type="button"
                  variant={isRecording ? "danger" : "default"}
                  className="w-full"
                  disabled={pending || transcribing || !micTranscriptionAvailable}
                  onClick={isRecording ? stopRecording : () => void startRecording()}
                >
                  {isRecording ? (
                    <>
                      <StopCircle className="h-4 w-4" />
                      Stop recording
                    </>
                  ) : (
                    <>
                      <Circle className="h-4 w-4" />
                      Record from microphone
                    </>
                  )}
                </Button>
              </div>
            ) : (
              <div className="space-y-3 rounded-[0.875rem] border border-border/60 bg-background/40 p-3">
                <div className="text-sm font-medium">Upload audio</div>
                {!micTranscriptionAvailable ? (
                  <div className="rounded-[0.75rem] border border-amber-500/30 bg-amber-500/10 px-2.5 py-2 text-xs text-amber-950 dark:text-amber-100">
                    Upload transcription requires OpenAI speech (OPENAI_API_KEY). You can still use Insert demo
                    transcript.
                  </div>
                ) : null}
                <div className="text-xs text-muted-foreground">
                  Supported formats: {formatMimeTypes(capabilities.supported_mime_types)}
                </div>
                <div className="text-xs text-muted-foreground">Max size: {capabilities.max_upload_mb} MB</div>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  disabled={pending || transcribing || !micTranscriptionAvailable}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-4 w-4" />
                  Choose audio file
                </Button>
              </div>
            )}
            {process.env.NODE_ENV === "development" && speechDevPanel ? (
              <div className="mt-3 max-h-48 overflow-auto rounded-[0.875rem] border border-dashed border-border/60 bg-muted/20 px-3 py-2 font-mono text-[10px] leading-relaxed text-muted-foreground">
                <div className="mb-1 font-sans text-[11px] font-semibold text-foreground">Speech debug (dev only)</div>
                <div>GET /speech/capabilities → provider_mode: {capabilities.provider_mode}</div>
                <div>openai_key_configured (backend): {String(capabilities.openai_key_configured)}</div>
                <div>microphone_transcription_available: {String(capabilities.microphone_transcription_available)}</div>
                {Object.entries(speechDevPanel).map(([key, value]) => (
                  <div key={key}>
                    {key}: {String(value)}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </Card>
  );
}

function cleanupRecording(
  recorderRef: MutableRefObject<MediaRecorder | null>,
  streamRef: MutableRefObject<MediaStream | null>,
  intervalRef: MutableRefObject<number | null>,
) {
  if (intervalRef.current != null) {
    window.clearInterval(intervalRef.current);
    intervalRef.current = null;
  }
  if (streamRef.current) {
    for (const track of streamRef.current.getTracks()) {
      track.stop();
    }
    streamRef.current = null;
  }
  recorderRef.current = null;
}

function pickRecorderMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") {
    return undefined;
  }
  for (const mimeType of RECORDER_MIME_PREFERENCE) {
    if (MediaRecorder.isTypeSupported(mimeType)) {
      return mimeType;
    }
  }
  return undefined;
}

function isMimeTypeSupported(fileMimeType: string, supportedMimeTypes: string[]): boolean {
  if (!fileMimeType) {
    return true;
  }
  const normalized = normalizeAudioMimeType(fileMimeType);
  return supportedMimeTypes.includes(normalized);
}

function normalizeAudioMimeType(fileMimeType: string): string {
  const base = fileMimeType.toLowerCase().split(";", 1)[0].trim();
  return MIME_TYPE_ALIASES[base] ?? base;
}

function buildAcceptList(supportedMimeTypes: string[]): string {
  const accept = new Set<string>(supportedMimeTypes);
  for (const alias of Object.keys(MIME_TYPE_ALIASES)) {
    accept.add(alias);
  }
  return Array.from(accept).join(",");
}

function formatMimeTypes(supportedMimeTypes: string[]): string {
  return supportedMimeTypes
    .map((mimeType) => mimeType.replace("audio/", "").toUpperCase())
    .join(", ");
}

function extensionFromMimeType(mimeType: string): string {
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mpeg")) return "mp3";
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0");
  const secs = (seconds % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function getMicrophoneErrorMessage(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError") {
      return "Microphone permission was denied. Use upload mode or allow access and retry.";
    }
    if (error.name === "NotFoundError") {
      return "No microphone was detected on this device. Use upload mode instead.";
    }
  }
  return "Microphone recording is unavailable in this browser. Use upload mode.";
}

function isQuotaExceededDetail(detail: unknown): boolean {
  if (!detail || typeof detail !== "object") return false;
  return (detail as Record<string, unknown>).error === "quota_exceeded";
}

function formatSpeechError(error: ApiError): string {
  const detail = error.detail;
  if (isQuotaExceededDetail(detail)) {
    const rec = detail as Record<string, unknown>;
    const planRaw = typeof rec.plan === "string" ? rec.plan : "free";
    const planLabel = planRaw.charAt(0).toUpperCase() + planRaw.slice(1);
    const reset = typeof rec.reset_at === "string" ? rec.reset_at.trim() : "";
    let msg = `You have used all monthly speech uploads on the ${planLabel} plan.\nUpgrade your plan or reset dev usage to continue testing.`;
    if (reset) {
      msg += `\n\nQuota resets (UTC): ${reset}.`;
    }
    return msg;
  }
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const code = typeof record.error === "string" ? record.error : "unknown_error";
    const hint = typeof record.hint === "string" ? record.hint : "";
    const message = typeof record.message === "string" ? record.message : "";
    const providerMode = typeof record.provider_mode === "string" ? record.provider_mode : "";
    const statusLine = `Status ${error.status} (${code})`;
    return [statusLine, message, hint, providerMode ? `Provider mode: ${providerMode}` : ""]
      .filter((item) => item.length > 0)
      .join(" — ");
  }
  return `Status ${error.status} — ${error.message}`;
}

function ThinkingState() {
  return (
    <div className="max-w-2xl rounded-[1rem] border border-border/70 bg-card/70 px-4 py-4">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        AlphaLens is building the investigation
      </div>
      <div className="mt-3 grid gap-2">
        <div className="h-3 w-40 rounded-full bg-muted" />
        <div className="h-3 w-full rounded-full bg-muted" />
        <div className="h-3 w-4/5 rounded-full bg-muted" />
      </div>
    </div>
  );
}

function ChatBubble({
  turn,
  conversationId,
}: {
  turn: ChatTurn;
  conversationId: string | null;
}) {
  const isAssistant = turn.message.role === "assistant";
  const useInvestmentCard = isAssistant && turn.answerType === "investment_decision";
  const technicalDetailsOpen =
    typeof process !== "undefined" && process.env.NEXT_PUBLIC_DEBUG_UI === "true";
  const executiveText = (turn.analysis?.final_answer ?? turn.message.content).trim();
  const needsMoreAnalysis = turn.decision?.recommendation === "needs_more_analysis";
  const lowConfidence =
    turn.decision != null && turn.decision.confidence < 0.45 && turn.decision.recommendation !== "needs_more_analysis";
  return (
    <div className={cn("flex gap-3", !isAssistant && "flex-row-reverse")}>
      {isAssistant && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-primary/12 text-primary">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
      )}
      <div
        className={cn(
          "space-y-3 rounded-[1rem] border px-4 py-3 text-sm",
          isAssistant && !useInvestmentCard ? "max-w-[min(36rem,88%)] border-border/60 bg-card/70" : null,
          isAssistant && useInvestmentCard
            ? "max-w-[88%] border-border/70 bg-card/80 text-foreground md:max-w-[82%]"
            : null,
          !isAssistant
            ? "max-w-[88%] border-primary/30 bg-primary text-primary-foreground shadow-[0_10px_20px_rgba(59,130,246,0.18)] md:max-w-[82%]"
            : null,
        )}
      >
        <div className="flex items-center justify-between gap-3">
          <div className={cn("text-[11px] font-semibold uppercase tracking-[0.18em]", isAssistant ? "text-muted-foreground" : "text-primary-foreground/75")}>
            {isAssistant ? "AlphaLens" : "You"}
          </div>
        </div>
        {isAssistant && useInvestmentCard ? <div className="section-label">Executive answer</div> : null}
        {isAssistant && useInvestmentCard ? (
          <p className="whitespace-pre-wrap leading-relaxed text-foreground">{executiveText}</p>
        ) : (
          <p className="whitespace-pre-wrap leading-relaxed">{turn.message.content}</p>
        )}
        {isAssistant && useInvestmentCard && turn.investigationId ? (
          <div className="rounded-[0.75rem] border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-900 dark:text-emerald-100">
            Investigation saved.{" "}
            <Link href="/investigations" className="underline">
              View investigation
            </Link>
          </div>
        ) : null}

        {isAssistant && useInvestmentCard && (needsMoreAnalysis || lowConfidence) ? (
          <div className="rounded-[0.875rem] border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
            <span className="font-semibold">More analysis required — </span>
            {needsMoreAnalysis
              ? "Evidence or confidence did not meet the bar for a firm recommendation."
              : "Confidence is low; corroborate with additional data before acting."}
          </div>
        ) : null}

        {isAssistant && useInvestmentCard && turn.analysis?.limitations && turn.analysis.limitations.length > 0 ? (
          <div className="space-y-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground/80">Limitations: </span>
            {turn.analysis.limitations.slice(0, 2).map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        ) : null}

        {isAssistant && useInvestmentCard && turn.decision ? (
          <div className="space-y-2">
            <div className="section-label">Recommendation</div>
            <div className="flex flex-wrap items-center gap-2">
              <RecommendationBadge recommendation={turn.decision.recommendation} />
              <RiskBadge level={turn.decision.risk_level} />
              <ConfidenceBadge value={turn.decision.confidence} />
              <ApprovalModeBadge requiresApproval={turn.decision.requires_approval} />
            </div>
          </div>
        ) : null}

        {isAssistant && useInvestmentCard && turn.decision && turn.decision.reasoning.length > 0 ? (
          <div>
            <div className="section-label">Key reasoning</div>
            <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
              {turn.decision.reasoning.map((line, idx) => (
                <li key={idx} className="rounded-lg bg-background/40 px-2.5 py-2">
                  {line}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {isAssistant && useInvestmentCard && turn.decision && turn.decision.evidence.length > 0 ? (
          <div>
            <div className="section-label">Key evidence</div>
            <ul className="mt-2 space-y-1.5 text-xs">
              {turn.decision.evidence.map((e, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 rounded-lg bg-background/40 px-2.5 py-2 text-muted-foreground"
                >
                  <Badge variant="outline" className="shrink-0 font-mono normal-case tracking-normal">
                    {e.tool}
                  </Badge>
                  <span className="min-w-0 flex-1">{e.summary}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {isAssistant && useInvestmentCard && turn.analysis && turn.analysis.rag_sources.length > 0 ? (
          <details className="rounded-[0.875rem] border border-border/60 bg-background/45 px-3 py-2">
            <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              RAG sources ({turn.analysis.rag_sources.length})
            </summary>
            <div className="mt-2 space-y-2">
              {turn.analysis.retrieval_mode ? (
                <div className="text-xs text-muted-foreground">Retrieval mode: {turn.analysis.retrieval_mode}</div>
              ) : null}
              {turn.analysis.rag_sources.map((source) => (
                <div key={source.chunk_id} className="rounded-lg border border-border/60 bg-card/50 px-2.5 py-2 text-xs">
                  <div className="font-medium text-foreground">{source.document_title}</div>
                  <div className="mt-0.5 text-muted-foreground">
                    {source.source ? `Path: ${source.source}` : "Knowledge base"} · Chunk {source.chunk_id} · Score{" "}
                    {source.score.toFixed(2)}
                  </div>
                  <div className="mt-1 max-h-24 overflow-hidden text-ellipsis text-muted-foreground">{source.snippet}</div>
                </div>
              ))}
            </div>
          </details>
        ) : null}

        {isAssistant &&
        useInvestmentCard &&
        (turn.citations?.length || turn.usedTools?.length || turn.analysis) ? (
          <details
            className="rounded-[0.875rem] border border-border/50 bg-background/35 px-3 py-2"
            open={technicalDetailsOpen}
          >
            <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Technical trace
            </summary>
            <div className="mt-3 space-y-3 text-xs">
              {turn.usedTools && turn.usedTools.length > 0 ? (
                <div>
                  <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Tools used
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {turn.usedTools.map((tool) => (
                      <Badge key={tool} variant="outline">
                        {tool.replaceAll("_", " ")}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}
              {turn.analysis && turn.analysis.rag_sources.length === 0 ? (
                <div className="text-muted-foreground">
                  RAG:{" "}
                  {turn.analysis.rag_status === "no_results"
                    ? "requested — no matching chunks."
                    : turn.analysis.rag_status === "unavailable"
                      ? "unavailable (Qdrant / retrieval)."
                      : turn.analysis.rag_status === "not_requested"
                        ? "not used."
                        : "status unknown."}
                </div>
              ) : null}
              {turn.analysis ? (
                <>
                  <AnalysisSection title="Provider mode">
                    <div className="flex flex-wrap gap-1.5">
                      {turn.analysis.provider_modes.map((mode) => (
                        <Badge key={mode.name} variant="outline">
                          {mode.name}: {mode.mode}
                        </Badge>
                      ))}
                    </div>
                  </AnalysisSection>
                  <AnalysisSection title="Data used">
                    {turn.analysis.data_used.length > 0 ? (
                      <ul className="space-y-1 text-muted-foreground">
                        {turn.analysis.data_used.map((item) => (
                          <li key={item}>- {item}</li>
                        ))}
                      </ul>
                    ) : (
                      <div className="text-muted-foreground">No external datasets were required.</div>
                    )}
                  </AnalysisSection>
                  {turn.analysis.limitations.length > 2 ? (
                    <AnalysisSection title="Further limitations">
                      <ul className="space-y-1 text-muted-foreground">
                        {turn.analysis.limitations.slice(2).map((item) => (
                          <li key={item}>- {item}</li>
                        ))}
                      </ul>
                    </AnalysisSection>
                  ) : null}
                </>
              ) : null}
              {turn.citations && turn.citations.length > 0 ? (
                <div>
                  <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Citations
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {turn.citations.map((c) => (
                      <Badge key={c.source_id} variant="muted" className="normal-case tracking-normal">
                        {c.title}
                      </Badge>
                    ))}
                  </div>
                </div>
              ) : null}
              {turn.routing?.suggested_tools && turn.routing.suggested_tools.length > 0 ? (
                <div className="text-muted-foreground">
                  Router suggested tools: {turn.routing.suggested_tools.join(", ")}
                </div>
              ) : null}
              {turn.analysis?.orchestration_trace ? (
                <div className="rounded-lg border border-border/60 bg-card/50 px-2.5 py-2 font-mono text-[11px] text-muted-foreground">
                  <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Orchestration
                  </div>
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-all">
                    {JSON.stringify(turn.analysis.orchestration_trace, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
          </details>
        ) : null}

        {useInvestmentCard && turn.decision ? (
          <DecisionCard
            decision={turn.decision}
            analysis={turn.analysis}
            conversationId={conversationId}
            responseId={turn.responseId ?? null}
            variant="footer"
          />
        ) : null}
      </div>
    </div>
  );
}

function AnalysisSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</div>
      {children}
    </div>
  );
}

function DecisionCard({
  decision,
  analysis,
  conversationId,
  responseId,
  variant = "full",
}: {
  decision: AgentDecision;
  analysis?: ChatResponse["analysis"];
  conversationId: string | null;
  responseId: string | null;
  /** When `footer`, badges and reasoning/evidence are shown above in the bubble. */
  variant?: "full" | "footer";
}) {
  const [feedback, setFeedback] = useState<FeedbackRating | null>(null);
  const [category, setCategory] = useState<FeedbackCategory>("usefulness");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [memoSubmitting, setMemoSubmitting] = useState(false);
  const [memoCreatedId, setMemoCreatedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submitFeedback = async (rating: FeedbackRating) => {
    if (!conversationId || !responseId || submitting || submitted) return;
    setFeedback(rating);
    setSubmitting(true);
    setError(null);
    try {
      await api.submitFeedback({
        conversation_id: conversationId,
        response_id: responseId,
        rating,
        comment: comment.trim() || null,
        category,
      });
      setSubmitted(true);
    } catch {
      setError("Could not save feedback right now.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleGenerateMemo = async () => {
    if (!conversationId || !responseId || memoSubmitting) return;
    setMemoSubmitting(true);
    setError(null);
    try {
      if (!analysis) {
        setError("Memo generation failed: missing analysis context for this response.");
        return;
      }
      const payload = buildInvestmentMemoReportPayload({
        conversationId: conversationId,
        responseId: responseId,
        decision,
        analysis,
      });
      const created = await api.createReport(payload);
      setMemoCreatedId(created.id);
    } catch (error) {
      setError(formatMemoReportError(error));
    } finally {
      setMemoSubmitting(false);
    }
  };

  const showPrimary = variant === "full";

  return (
    <div className="rounded-[0.875rem] border border-border/70 bg-background/60 p-3 text-foreground">
      {showPrimary ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <RecommendationBadge recommendation={decision.recommendation} />
            <RiskBadge level={decision.risk_level} />
            <ConfidenceBadge value={decision.confidence} />
            <ApprovalModeBadge requiresApproval={decision.requires_approval} />
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            <MiniStat label="Evidence" value={String(decision.evidence.length)} />
            <MiniStat label="Confidence" value={`${(decision.confidence * 100).toFixed(0)}%`} />
          </div>
        </>
      ) : null}
      {decision.disclaimer && (
        <div className="mt-3 rounded-[0.75rem] border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-950 dark:text-amber-100">
          {decision.disclaimer}
        </div>
      )}
      {decision.approval_required_reason && (
        <div className="mt-2 text-xs text-muted-foreground">
          Approval reason: {decision.approval_required_reason}
        </div>
      )}
      {decision.policy_flags && decision.policy_flags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {decision.policy_flags.map((flag) => (
            <Badge key={flag} variant="outline" className="capitalize">
              {flag.replaceAll("_", " ")}
            </Badge>
          ))}
        </div>
      )}

      {showPrimary && decision.intent ? (
        <div className="mt-3 rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-3 text-xs">
          <div className="section-label">Intent</div>
          <div className="mt-1 text-foreground">{decision.intent}</div>
        </div>
      ) : null}

      {showPrimary && decision.reasoning.length > 0 ? (
        <div className="mt-3">
          <div className="section-label">Key reasoning</div>
          <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
            {decision.reasoning.slice(0, 3).map((line, idx) => (
              <li key={idx} className="rounded-lg bg-background/40 px-2.5 py-2">
                {line}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {showPrimary && decision.evidence.length > 0 ? (
        <div className="mt-3">
          <div className="section-label">Key evidence</div>
          <ul className="mt-2 space-y-1.5 text-xs">
            {decision.evidence.slice(0, 4).map((e, idx) => (
              <li key={idx} className="flex items-start gap-2 rounded-lg bg-background/40 px-2.5 py-2 text-muted-foreground">
                <Badge variant="outline" className="shrink-0 font-mono normal-case tracking-normal">
                  {e.tool}
                </Badge>
                <span className="min-w-0 flex-1">{e.summary}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {showPrimary ? (
        <details className="mt-3 rounded-[0.875rem] border border-border/50 bg-background/35 px-3 py-2 text-xs">
          <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Decision technical details
          </summary>
          <div className="mt-3 space-y-3 text-muted-foreground">
            {decision.approval_id ? (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-[11px] break-all">Approval ID: {decision.approval_id}</span>
                <Button asChild size="sm" variant="outline">
                  <Link href="/approvals">
                    View approval
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                </Button>
              </div>
            ) : (
              <div>Approval ID: none</div>
            )}
            {decision.reasoning.length > 3 ? (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em]">Full reasoning</div>
                <ul className="space-y-1.5">
                  {decision.reasoning.slice(3).map((line, idx) => (
                    <li key={idx} className="rounded-lg bg-background/40 px-2.5 py-2">
                      {line}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {decision.evidence.length > 4 ? (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em]">Further evidence</div>
                <ul className="space-y-1.5">
                  {decision.evidence.slice(4).map((e, idx) => (
                    <li key={idx} className="flex items-start gap-2 rounded-lg bg-background/40 px-2.5 py-2">
                      <Badge variant="outline" className="shrink-0 font-mono normal-case tracking-normal">
                        {e.tool}
                      </Badge>
                      <span className="min-w-0 flex-1">{e.summary}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {analysis?.orchestration_trace ? (
              <div className="rounded-lg border border-border/60 bg-card/50 px-2.5 py-2">
                <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  <Info className="h-3.5 w-3.5" />
                  How this answer was produced
                </div>
                <ul className="space-y-1">
                  <li>1. Intent detected: {String(analysis.orchestration_trace.intent_detected ?? analysis.intent)}</li>
                  <li>
                    2. Tools selected:{" "}
                    {Array.isArray(analysis.orchestration_trace.tools_selected)
                      ? analysis.orchestration_trace.tools_selected.join(", ")
                      : analysis.tools_used.join(", ") || "none"}
                  </li>
                  <li>
                    3. Evidence gathered:{" "}
                    {Array.isArray(analysis.orchestration_trace.evidence_gathered)
                      ? analysis.orchestration_trace.evidence_gathered.join(", ")
                      : analysis.evidence_items.map((item) => item.title).join(", ") || "none"}
                  </li>
                  <li>4. RAG retrieval status: {String(analysis.orchestration_trace.rag_retrieval_status ?? analysis.rag_status ?? "unknown")}</li>
                  <li>5. Synthesis mode: {String(analysis.orchestration_trace.synthesis_mode ?? "deterministic_fallback")}</li>
                  <li>6. Approval gate result: {String(analysis.orchestration_trace.approval_gate_result ?? "n/a")}</li>
                </ul>
              </div>
            ) : null}
          </div>
        </details>
      ) : (
        <div className="mt-3 space-y-2 text-xs text-muted-foreground">
          {decision.approval_id ? (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-[0.75rem] border border-border/60 bg-card/50 px-2.5 py-2">
              <span className="font-mono text-[11px] break-all">Approval ID: {decision.approval_id}</span>
              <Button asChild size="sm" variant="outline">
                <Link href="/approvals">
                  View approval
                  <ExternalLink className="h-3.5 w-3.5" />
                </Link>
              </Button>
            </div>
          ) : null}
        </div>
      )}

      {conversationId && responseId && (
        <div className="mt-3 flex flex-col gap-3 rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs text-muted-foreground">
            Generate a structured memo from this decision context.
            {decision.evidence.length === 0 ? (
              <div className="mt-1 text-amber-600 dark:text-amber-300">
                Memo will be limited because this answer has no structured evidence.
              </div>
            ) : null}
          </div>
          <div className="flex items-center gap-2">
            {memoCreatedId && (
              <Button asChild size="sm" variant="subtle">
                <Link href="/reports">Open report</Link>
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={() => void handleGenerateMemo()}>
              {memoSubmitting ? "Generating..." : "Generate memo"}
            </Button>
          </div>
        </div>
      )}

      {conversationId && responseId && (
        <div className="mt-3 rounded-[0.875rem] border border-border/60 bg-card/60 p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="section-label">Feedback</div>
              <div className="text-xs text-muted-foreground">
                Rate this answer to improve future recommendations.
              </div>
            </div>
            {submitted ? (
              <Badge variant="success">Submitted</Badge>
            ) : (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={submitting}
                  onClick={() => void submitFeedback("thumbs_up")}
                >
                  👍
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={submitting}
                  onClick={() => void submitFeedback("thumbs_down")}
                >
                  👎
                </Button>
              </div>
            )}
          </div>

          {feedback && !submitted && (
            <div className="mt-3 space-y-2">
              <select
                value={category}
                onChange={(event) => setCategory(event.target.value as FeedbackCategory)}
                className="h-11 w-full rounded-[0.875rem] border border-border bg-background px-3 text-sm"
              >
                {["usefulness", "accuracy", "clarity", "risk", "other"].map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <textarea
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="Optional comment"
                className="min-h-24 w-full rounded-[0.875rem] border border-border bg-background px-3 py-2.5 text-sm"
              />
              <Button size="sm" onClick={() => void submitFeedback(feedback)}>
                {submitting ? "Saving..." : "Submit feedback"}
              </Button>
            </div>
          )}
          {submitted ? (
            <div className="mt-2 text-xs text-muted-foreground">
              Feedback saved. It is stored with this response ID and appears in Usage feedback analytics.
            </div>
          ) : null}
          {error && <div className="mt-2 text-xs text-destructive">{error}</div>}
        </div>
      )}
    </div>
  );
}

function MiniStat({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-[0.875rem] border border-border/60 bg-card/60 px-2.5 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-sm font-medium text-foreground", mono && "font-mono")}>
        {value}
      </div>
    </div>
  );
}
