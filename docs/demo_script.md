# Demo Script (5 Minutes)

## 1) Product Opening (30s)

“AlphaLens AI is an agentic investment intelligence platform for portfolio decision support. It combines structured AI orchestration, hybrid RAG, provider fallbacks, and human approvals in one full-stack workflow.”

## 2) Dashboard (30s)

Open dashboard and show:
- portfolio snapshot and risk metrics;
- key holdings and status signals;
- approvals/usage summary cards.

## 3) Runtime Status and Fallback Explanation (30s)

Open settings/runtime area and explain:
- runtime health and provider status;
- fallback mode availability for reliable demos;
- deterministic behavior when external keys are not configured.

## 4) Knowledge Base and RAG (40s)

Open knowledge base page and show:
- seeded internal documents;
- upload capability;
- how indexed docs are later cited by the agent.

Prompt:
```text
Summarize the internal investment policy from the knowledge base.
```

## 5) Agent Chat (90s)

Run prompts in chat:

```text
What has been the performance of the portfolio in the last 1 month?
```

```text
Which policy rules are currently breached by the portfolio?
```

```text
Use RAG and internal policy documents to explain whether NVDA should be trimmed.
```

Call out response structure:
- final answer;
- tools used;
- RAG sources;
- provider mode;
- limitations/compliance metadata.

## 6) Human Approval Workflow (30s)

Open approvals page and show:
- pending/approved/rejected states;
- reviewer action options;
- audit-oriented decision tracking.

## 7) Reports (20s)

Open reports page and show generated investment memo/report artifact from chat context.

## 8) Scenarios (20s)

Open scenarios page and run or show a deterministic scenario result and portfolio impact summary.

## 9) Speech Transcription (20s)

Show speech input/transcription support (or disabled state in fallback mode) and explain it feeds into the same agent pipeline.

## 10) Usage and Feedback (20s)

Open usage page and feedback controls:
- event and cost visibility;
- feedback loop for response quality monitoring.

## 11) Architecture Close (10s)

End on architecture/docs summary:
- FastAPI backend + Next.js frontend;
- LangGraph orchestration + tool layer + fallback providers;
- Postgres, Redis, Qdrant data stack;
- CI-validated, Docker-ready project structure.
