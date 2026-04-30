"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import {
  ExternalLink,
  Loader2,
  Mic,
  Send,
  Sparkles,
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
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  AgentDecision,
  ChatMessage,
  Citation,
  FeedbackCategory,
  FeedbackRating,
  TranscriptionResult,
} from "@/types/api";

interface ChatTurn {
  id: string;
  message: ChatMessage;
  citations?: Citation[];
  decision?: AgentDecision | null;
  responseId?: string | null;
  usedTools?: string[];
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

export function ChatPanel() {
  const [turns, setTurns] = useState<ChatTurn[]>(SEED);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speechError, setSpeechError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

    try {
      const response = await api.chat({
        conversation_id: conversationId,
        messages: [...turns, userTurn].map((t) => t.message),
      });
      setConversationId(response.conversation_id);
      setTurns((prev) => [
        ...prev,
        {
          id: `a_${Date.now()}`,
          message: response.message,
          citations: response.citations,
          decision: response.decision ?? null,
          responseId: response.response_id,
          usedTools: response.used_tools,
        },
      ]);
    } finally {
      setPending(false);
    }
  };

  const handleAudioUpload = async (file: File) => {
    if (pending || transcribing) return;
    setSpeechError(null);
    setTranscribing(true);
    try {
      const result: TranscriptionResult = await api.transcribeSpeech(file);
      setInput(result.text);
    } catch {
      setSpeechError("Transcription failed. Please try another audio file.");
    } finally {
      setTranscribing(false);
    }
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
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Portfolio</Badge>
              <Badge variant="outline">Policy</Badge>
              <Badge variant="outline">Market</Badge>
              <Badge variant="outline">News</Badge>
              <Badge variant="outline">Macro</Badge>
              <Badge variant="outline">SEC</Badge>
              <Badge variant="outline">RAG</Badge>
            </div>
          </div>
        </div>

        <ScrollArea className="flex-1 px-4 md:px-6">
          <div className="space-y-4 py-5">
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
                  Transcribing uploaded audio
                </div>
                <p className="mt-1 text-primary/80">
                  AlphaLens is extracting the question so you can review it before sending.
                </p>
              </div>
            )}
            {speechError && (
              <ErrorBanner
                title="Audio upload failed"
                message={speechError}
                className="max-w-2xl"
              />
            )}
          </div>
        </ScrollArea>
        <div className="border-t border-border/70 px-4 py-4 md:px-6">
          <form onSubmit={handleSubmit} className="rounded-[1rem] border border-border/70 bg-background/75 p-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              className="hidden"
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
                    {pending ? "Waiting for response..." : transcribing ? "Transcription in progress..." : "Ready"}
                  </span>
                </div>
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about portfolio, risk, research notes, or pending approvals..."
                  disabled={pending || transcribing}
                />
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={pending || transcribing}
                  onClick={() => fileInputRef.current?.click()}
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
    </Card>
  );
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
        <p className="whitespace-pre-wrap leading-relaxed">{turn.message.content}</p>

        {isAssistant && (turn.citations?.length || turn.usedTools?.length) ? (
          <div className="space-y-2 rounded-[0.875rem] border border-border/60 bg-background/45 p-3">
            {turn.usedTools && turn.usedTools.length > 0 ? (
              <div>
                <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  <WandSparkles className="h-3.5 w-3.5" />
                  Investigation steps
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
            conversationId={conversationId}
            responseId={turn.responseId ?? null}
          />
        )}
      </div>
    </div>
  );
}

function DecisionCard({
  decision,
  conversationId,
  responseId,
}: {
  decision: AgentDecision;
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

      {decision.intent && (
        <div className="mt-3 rounded-[0.875rem] border border-border/60 bg-card/60 px-3 py-3 text-xs">
          <div className="section-label">Intent</div>
          <div className="mt-1 text-foreground">{decision.intent}</div>
        </div>
      )}

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
