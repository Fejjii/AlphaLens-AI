# Demo Script

This script is designed for a 7 to 10 minute reviewer walkthrough of AlphaLens
AI and maps directly to the product workflow and validation package.

## Demo Goal

Show that AlphaLens is a production-minded investment intelligence workflow:

- authenticated user journey (register/login)
- plan-aware usage controls and quota visibility
- agent recommendations with compliance metadata
- human approval and audit path
- memo and scenario outputs
- feedback and usage observability
- deterministic fallback behavior without live provider keys

## Before You Start

- Start full stack (`docker compose up --build`) or run backend/frontend locally.
- Confirm frontend (`http://localhost:3000`) and backend health (`/health`).
- Keep fallback providers enabled if external keys are unavailable.
- Have `docs/validation_report.md`, CI workflows in `.github/workflows`, and
  `docs/deployment.md` available for final reviewer questions.

## Suggested Timing

1. Auth and dashboard framing: 60 to 90 seconds
2. Plan badge, quota, and settings context: 45 to 60 seconds
3. Agent chat and compliance metadata: 90 to 120 seconds
4. Approval workflow: 60 to 90 seconds
5. Memo generation: 45 to 60 seconds
6. Scenario simulation: 45 to 60 seconds
7. Feedback and usage dashboard: 60 to 90 seconds
8. CI/CD and deployment wrap-up: 30 to 45 seconds

## Demo Flow

### 1. Login / Register

Open `/register`, create a user, then log in at `/login`.

Narrate:

> AlphaLens starts with authenticated access so plans, approvals, reports,
> scenarios, and usage telemetry are scoped to the current user.

Show:

- registration success
- login success
- authenticated app shell navigation

### 2. Dashboard framing

Open `/` and frame the platform:

> AlphaLens combines portfolio visibility, agent investigation, approval gates,
> reports, scenarios, and cost-aware observability in one product workflow.

Show:

- NAV / day P&L / risk metrics
- top holdings and risk signals
- pending approvals and usage snapshot

### 3. Plan badge and quota

Open `/settings` briefly before chat.

Show:

- current plan badge
- monthly quota usage rows
- enabled tool/model capability chips

Narrate:

> The UI surfaces plan and quota context before execution so reviewers can
> evaluate both behavior and policy constraints.

### 4. Agent chat + compliance metadata

Open `/chat` (or `/agent`) and run:

```text
Review NVDA in the context of our portfolio. Recommend buy/hold/trim with
concentration risk, macro/market context, and approval rationale.
```

Show on the response card:

- recommendation, risk, confidence
- evidence and tool usage
- compliance metadata (`policy_flags`, `approval_required_reason`,
  `requires_approval`)

Narrate:

> AlphaLens does not only generate text; it returns structured decision metadata
> for governance and auditability.

### 5. Approval workflow

Open `/approvals`.

Show:

- pending item details and rationale
- status lifecycle (`pending`, `approved`, `rejected`, `needs_more_analysis`)
- reviewer action buttons and notes path

### 6. Memo generation

Open `/reports` and generate an investment memo:

```text
Create an investment memo for NVDA including thesis, risk controls, and
approval considerations.
```

Show:

- report type and generated sections
- citations/evidence references
- reviewable memo structure

### 7. Scenario simulation

Open `/scenarios` and run a deterministic scenario, for example:

- type: `price_shock`
- ticker: `NVDA`
- shock: `-0.10`

Show:

- simulated portfolio impact
- affected holdings
- scenario recommendation and risk framing

### 8. Feedback loop + usage/cost dashboard

In chat, submit thumbs up/down feedback on a response.
Then open `/usage`.

Show:

- total events and estimated cost
- event breakdown (LLM/tool/cache/report/feedback)
- provider/tool level visibility

Narrate:

> Feedback and usage are first-class outputs, enabling evaluation and safe
> iteration instead of opaque model behavior.

### 9. Settings / tools / providers

Return to `/settings` and call out:

- provider status indicators
- tool toggles
- runtime endpoint / proxy posture
- deterministic fallback readiness

### 10. CI/CD and deployment package

Close with repository evidence:

- CI workflows in `.github/workflows` (backend, frontend, docker, security)
- deployment guide in `docs/deployment.md`
- final checks in `docs/validation_report.md`

## Prompt Set (Quick Copy)

```text
Review NVDA in the context of our portfolio. Recommend buy/hold/trim with concentration risk, macro/market context, and approval rationale.
```

```text
Would this recommendation require human approval under a conservative policy workflow? Explain policy flags.
```

```text
Create an investment memo for NVDA including thesis, risk controls, and approval considerations.
```

```text
Simulate a -10% NVDA price shock and summarize impact by holdings and recommended response.
```

## Closing Line

> AlphaLens demonstrates an end-to-end AI workflow for investment review:
> authenticated access, plan-aware controls, structured and auditable decisions,
> human approvals, measurable usage, and deterministic fallback stability.
