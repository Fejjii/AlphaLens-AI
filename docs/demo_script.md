# Demo Script (5-7 Minutes)

## 1) Login and Dashboard (30-45s)

Open login and land on dashboard.

Presenter notes:
- Position AlphaLens as an agentic decision support platform, not a trading bot.
- Point out portfolio snapshot and governance-aware workflow.

## 2) Portfolio Overview (30-45s)

Show holdings, concentration view, and risk framing.

Presenter notes:
- Explain this is the baseline context used by the agent for portfolio questions.

## 3) Agent Chat: App Help (20-30s)

Ask:

```text
How many languages do you support?
```

Presenter notes:
- Show app-help route behavior.
- Confirm no investment actions (for example, no memo CTA in app-help mode).

## 4) Agent Chat: RAG Investment Question (60-75s)

Ask:

```text
Use RAG and internal policy documents to explain whether NVDA should be trimmed.
```

Presenter notes:
- Highlight clean executive answer quality.
- Call out evidence and source traceability.

## 5) Show Evidence + Trace (30-45s)

Expand response metadata:

- Evidence
- RAG sources (collapsed/expandable)
- Approval gate indicator
- Technical trace (collapsed)

Presenter notes:
- Mention selected/executed/skipped tool trace and limitations.

## 6) Generate Memo (20-30s)

Trigger memo generation from the investment response.

Presenter notes:
- Emphasize context-specific memo generation, not generic template output.

## 7) Reports Page (20-30s)

Open Reports and show the generated memo artifact.

Presenter notes:
- Confirm report persisted with context from the originating decision.

## 8) Investigations Timeline (20-30s)

Open Investigations and show persisted timeline entry linked to the decision run.

Presenter notes:
- Position this as auditability and post-hoc review support.

## 9) Scenario Prompt in Chat (30-45s)

Ask:

```text
What happens if NVDA drops 10 percent?
```

Presenter notes:
- Explain scenario-style chat uses first-order portfolio impact fallback when needed.

## 10) Scenarios Page (20-30s)

Open Scenarios page and explain manual simulation workflow.

## 11) Approvals (20-30s)

Open Approvals page and show approve/reject/needs-more-analysis states.

## 12) Usage and Feedback (20-30s)

Open Usage/Feedback views and show operational observability.

## 13) Close with Architecture Story (20-30s)

Close with:

- Next.js frontend + FastAPI backend
- LangGraph orchestration with router-driven tool selection
- Postgres + Redis + Qdrant data layer
- Human-in-the-loop governance and persisted investigation/report trails
