# Demo Script

This script is designed for a 5 to 7 minute reviewer walkthrough of AlphaLens
AI. It follows the product narrative from portfolio visibility to agent
investigation, human approval, memo generation, scenario analysis, usage
tracking, and system controls.

## Demo Goal

Show that AlphaLens is a polished investment intelligence workflow, not just a
chatbot:

- grounded in portfolio and research context,
- capable of structured decision support,
- explicit about evidence and tool use,
- safe through human approval,
- measurable through usage and feedback,
- stable in deterministic demo mode.

## Before You Start

- Start the frontend and backend, or the Docker full stack.
- Confirm the dashboard loads.
- If live providers are not configured, keep fallback mode enabled. The demo is
  designed to work in deterministic mode.

## Suggested Timing

1. Dashboard framing: 45 to 60 seconds
2. Chat question and decision card: 90 to 120 seconds
3. Approval queue: 45 to 60 seconds
4. Memo generation: 45 to 60 seconds
5. Scenario simulation: 45 to 60 seconds
6. Usage, feedback, settings: 60 to 90 seconds

## Demo Flow

### 1. Dashboard

Open `/` and say:

> AlphaLens brings portfolio monitoring, agent investigation, approvals,
> reports, scenarios, and usage tracking into a single reviewer-facing product.

Call out:

- NAV, day P&L, and risk metrics
- top positions and alerts
- pending approvals preview
- usage visibility on the main dashboard

### 2. Chat Investment Question

Open `/chat` or `/agent` and use this sample prompt:

```text
Review NVDA in the context of our current portfolio. Should we add, trim, or hold?
Include portfolio concentration, market context, macro signals, SEC filing context,
and any relevant research evidence.
```

Narrate:

> This is where AlphaLens investigates across portfolio, policy, market, news,
> macro, SEC, and retrieval-backed research context in one thread.

What to show:

- assistant answer
- evidence badges
- tool/investigation steps
- decision card

### 3. Decision Card

Stay on the same chat result and point to:

- recommendation
- risk badge
- confidence badge
- approval state
- evidence and reasoning summary

Suggested narration:

> The decision card makes the model output reviewable. It separates the answer
> from the action recommendation, confidence, evidence, and approval state.

If a second prompt is helpful, use:

```text
Would this recommendation require human approval under a conservative risk workflow?
```

### 4. Approval Request

Open `/approvals`.

Suggested narration:

> AlphaLens does not assume autonomy is enough. Recommendations that warrant
> review are routed into a human-in-the-loop approval queue with audit-friendly
> state tracking.

What to show:

- approval status
- rationale
- audit trail
- approve / reject / more analysis actions

If there is a pending item, click one of the actions and explain the updated
state. If you prefer not to mutate state during the demo, just describe the
action row and current approval status.

### 5. Memo Generation

Return to the decision card in chat or open `/reports`.

If using chat, click `Generate memo`.

If using the reports page directly, use this sample prompt:

```text
Create an investment memo for NVDA based on the current portfolio context,
including concentration risk, supporting evidence, and approval considerations.
```

Narrate:

> AlphaLens can convert a chat investigation into a structured artifact that is
> easier to review, share, and compare than a raw transcript.

What to show:

- report type
- generated sections
- concise memo structure

### 6. Scenario Simulation

Open `/scenarios`.

Use a deterministic sample scenario such as:

- scenario type: `price shock`
- ticker: `NVDA`
- shock percent: `-0.10`
- assumptions:

```text
AI infrastructure demand remains strong
Concentration risk remains elevated
Review impact under current portfolio weights
```

Narrate:

> Scenarios turn the conversation from recommendation into what-if analysis.
> This is especially useful for reviewer evaluation because the behavior is
> deterministic and easy to compare.

What to show:

- portfolio impact
- affected holdings
- recommendation
- approval-required signal if present

### 7. Usage and Cost Dashboard

Open `/usage`.

Narrate:

> AlphaLens treats observability as a product concern, not just an engineering
> concern. Reviewers can inspect event types, tool usage, provider activity,
> estimated cost, and user feedback in one place.

What to show:

- estimated cost
- total events
- event table
- provider or tool breakdown
- feedback summary

### 8. Feedback Loop

Return to chat and show the thumbs up / thumbs down controls on a response.

Suggested narration:

> Review feedback is captured directly at the response level, which creates a
> path toward evaluation, ranking, and future tuning.

### 9. Settings, Tools, and Providers

Open `/settings`.

Narrate:

> The settings surface makes the runtime posture legible: model selection,
> enabled tools, provider status, and deterministic fallback-friendly
> configuration.

Call out:

- provider availability
- tool toggles
- local/demo runtime endpoint
- deterministic fallback posture

## Exact Prompt Set

Use any or all of the following during the walkthrough.

### Primary investment question

```text
Review NVDA in the context of our current portfolio. Should we add, trim, or hold?
Include portfolio concentration, market context, macro signals, SEC filing context,
and any relevant research evidence.
```

### Approval framing

```text
Would this recommendation require human approval under a conservative risk workflow?
Explain why.
```

### Memo prompt

```text
Create an investment memo for NVDA based on the current portfolio context,
including concentration risk, supporting evidence, and approval considerations.
```

### Alternative chat prompt

```text
Compare trimming NVDA versus holding it. Focus on portfolio concentration,
recent market signals, macro backdrop, and risk-control implications.
```

## Closing Line

End with:

> AlphaLens is designed to show what a production-minded financial AI workflow
> looks like: grounded context, structured decisions, human approval, measurable
> usage, and deterministic demo stability.
