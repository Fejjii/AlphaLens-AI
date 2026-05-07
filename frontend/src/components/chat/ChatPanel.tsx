"use client";

import Link from "next/link";
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
  WandSparkles,
  Wrench,
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
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  AgentDecision,
  ChatMessage,
  Citation,
  ChatResponse,
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

export function ChatPanel() {
  const [turns, setTurns] = useState<ChatTurn[]>(SEED);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
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

  useEffect(() => {
    capabilitiesRef.current = capabilities;
  }, [capabilities]);

  useEffect(() => {
    inputValueRef.current = input;
  }, [input]);

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

  const refreshSpeechCapabilities = useCallback(() => {
    void api.speechCapabilities().then(setCapabilities).catch(() => undefined);
  }, []);

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
    if (!content || pending) return;

    const userTurn: ChatTurn = {
      id: `u_${Date.now()}`,
      message: { role: "user", content },
    };
    setTurns((prev) => [...prev, userTurn]);
    setInput("");
    setPending(true);
    setChatError(null);

    try {
      const response = await api.chat({
        conversation_id: conversationId,
        messages: [...turns, userTurn].map((t) => t.message),
      });
      const finalAnswer = response.analysis?.final_answer?.trim();
      const renderedContent = finalAnswer || response.message?.content?.trim() || "";
      if (!renderedContent) {
        setChatError(
          process.env.NODE_ENV === "development"
            ? "Malformed agent response: final_answer missing"
            : "Agent response is incomplete.",
        );
        return;
      }
      setConversationId(response.conversation_id);
      setTurns((prev) => [
        ...prev,
        {
          id: `a_${Date.now()}`,
          message: {
            ...response.message,
            content: renderedContent,
          },
          citations: response.citations,
          decision: response.decision ?? null,
          responseId: response.response_id,
          usedTools: response.used_tools,
          analysis: response.analysis,
        },
      ]);
    } catch (error) {
      if (error instanceof ApiError && error.message.trim()) {
        setChatError(error.message);
      } else {
        setChatError("Chat request failed. Check backend and retry.");
      }
    } finally {
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
  return (
    <div className={cn("flex gap-3", !isAssistant && "flex-row-reverse")}>
      {isAssistant && (
        <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-primary/12 text-primary">
          <Sparkles className="h-3.5 w-3.5" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[88%] space-y-3 rounded-[1rem] border px-4 py-3 text-sm md:max-w-[82%]",
          isAssistant
            ? "border-border/70 bg-card/80 text-foreground"
            : "border-primary/30 bg-primary text-primary-foreground shadow-[0_10px_20px_rgba(59,130,246,0.18)]",
        )}
      >
        <div className="flex items-center justify-between gap-3">
          <div className={cn("text-[11px] font-semibold uppercase tracking-[0.18em]", isAssistant ? "text-muted-foreground" : "text-primary-foreground/75")}>
            {isAssistant ? "AlphaLens" : "You"}
          </div>
          {isAssistant && turn.usedTools && turn.usedTools.length > 0 ? (
            <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <Wrench className="h-3 w-3" />
              {turn.usedTools.length} tools
            </div>
          ) : null}
        </div>
        {isAssistant ? <div className="section-label">Executive answer</div> : null}
        <p className="whitespace-pre-wrap leading-relaxed">{turn.message.content}</p>

        {isAssistant && (turn.citations?.length || turn.usedTools?.length || turn.analysis) ? (
          <div className="space-y-2 rounded-[0.875rem] border border-border/60 bg-background/45 p-3">
            {turn.usedTools && turn.usedTools.length > 0 ? (
              <div>
                <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  <WandSparkles className="h-3.5 w-3.5" />
                  Tools used in this answer
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

            {turn.analysis ? (
              <>
                <AnalysisSection title="RAG sources used">
                  {turn.analysis.retrieval_mode ? (
                    <div className="mb-2 text-xs text-muted-foreground">
                      Retrieval mode: {turn.analysis.retrieval_mode}
                    </div>
                  ) : null}
                  {turn.analysis.rag_sources.length > 0 ? (
                    <div className="space-y-2">
                      {turn.analysis.rag_sources.map((source) => (
                        <div key={source.chunk_id} className="rounded-lg border border-border/60 bg-card/50 px-2.5 py-2 text-xs">
                          <div className="font-medium">{source.document_title}</div>
                          <div className="mt-0.5 text-muted-foreground">
                            Source: {source.source ?? "knowledge"} · Chunk: {source.chunk_id} · Score: {source.score.toFixed(2)}
                          </div>
                          <div className="mt-1 text-muted-foreground">{source.snippet}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      {turn.analysis.rag_status === "no_results"
                        ? "RAG requested but no chunks matched this query."
                        : turn.analysis.rag_status === "unavailable"
                          ? "RAG unavailable. Qdrant or retrieval service is not connected."
                          : turn.analysis.rag_status === "not_requested"
                            ? "RAG was not requested for this answer."
                            : "RAG status unavailable."}
                    </div>
                  )}
                </AnalysisSection>
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
                    <ul className="space-y-1 text-xs text-muted-foreground">
                      {turn.analysis.data_used.map((item) => (
                        <li key={item}>- {item}</li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-xs text-muted-foreground">No external datasets were required.</div>
                  )}
                </AnalysisSection>
                <AnalysisSection title="Limitations">
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {turn.analysis.limitations.map((item) => (
                      <li key={item}>- {item}</li>
                    ))}
                  </ul>
                </AnalysisSection>
              </>
            ) : null}

            {turn.citations && turn.citations.length > 0 ? (
              <div>
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Evidence
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
          </div>
        ) : null}

        {turn.decision && (
          <DecisionCard
            decision={turn.decision}
            analysis={turn.analysis}
            conversationId={conversationId}
            responseId={turn.responseId ?? null}
          />
        )}
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
}: {
  decision: AgentDecision;
  analysis?: ChatResponse["analysis"];
  conversationId: string | null;
  responseId: string | null;
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
      const created = await api.createReport({
        report_type: "investment_memo",
        conversation_id: conversationId,
        source_response_id: responseId,
        ticker: inferTicker(decision),
        prompt: `Generate memo for ${decision.recommendation} recommendation with ${decision.risk_level} risk and ${decision.confidence.toFixed(2)} confidence.`,
      });
      setMemoCreatedId(created.id);
    } catch {
      setError("Could not generate memo from this response.");
    } finally {
      setMemoSubmitting(false);
    }
  };

  return (
    <div className="rounded-[0.875rem] border border-border/70 bg-background/60 p-3 text-foreground">
      <div className="flex flex-wrap items-center gap-2">
        <RecommendationBadge recommendation={decision.recommendation} />
        <RiskBadge level={decision.risk_level} />
        <ConfidenceBadge value={decision.confidence} />
        <ApprovalModeBadge requiresApproval={decision.requires_approval} />
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <MiniStat label="Approval" value={decision.approval_id ?? "none"} mono />
        <MiniStat label="Evidence" value={String(decision.evidence.length)} />
        <MiniStat label="Confidence" value={`${(decision.confidence * 100).toFixed(0)}%`} />
      </div>
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

      {decision.intent && (
        <div className="mt-3 rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-3 text-xs">
          <div className="section-label">Intent</div>
          <div className="mt-1 text-foreground">{decision.intent}</div>
        </div>
      )}

      {analysis?.orchestration_trace ? (
        <div className="mt-3 rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-3 text-xs">
          <div className="mb-2 flex items-center gap-2 section-label">
            <Info className="h-3.5 w-3.5" />
            How this answer was produced
          </div>
          <ul className="space-y-1 text-muted-foreground">
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

      {decision.reasoning.length > 0 && (
        <div className="mt-3">
          <div className="section-label">Reasoning</div>
          <ul className="mt-2 space-y-1.5 text-xs text-muted-foreground">
            {decision.reasoning.map((line, idx) => (
              <li key={idx} className="rounded-lg bg-background/40 px-2.5 py-2">
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}

      {decision.evidence.length > 0 && (
        <div className="mt-3">
          <div className="section-label">Evidence and tools</div>
          <ul className="mt-2 space-y-1.5 text-xs">
            {decision.evidence.map((e, idx) => (
              <li key={idx} className="flex items-start gap-2 rounded-lg bg-background/40 px-2.5 py-2 text-muted-foreground">
                <Badge variant="outline" className="shrink-0 font-mono normal-case tracking-normal">
                  {e.tool}
                </Badge>
                <span className="min-w-0 flex-1">{e.summary}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {decision.approval_id && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <span className="font-mono text-xs text-muted-foreground">
            {decision.approval_id}
          </span>
          <Button asChild size="sm" variant="outline">
            <Link href="/approvals">
              View Approval
              <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </Button>
        </div>
      )}

      {conversationId && responseId && (
        <div className="mt-3 flex flex-col gap-3 rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs text-muted-foreground">
            Generate a structured memo from this decision context.
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

function inferTicker(decision: AgentDecision): string | null {
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
