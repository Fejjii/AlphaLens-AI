# AlphaLens AI

AlphaLens AI is a demo-ready agentic investment intelligence platform for
reviewing portfolio risk, generating investment memos, routing decisions
through human approval, and tracking model/tool usage in a polished SaaS
interface.

It combines a FastAPI backend, a Next.js frontend, LangGraph-based agent
orchestration, retrieval-augmented context, and deterministic fallbacks so the
full product remains evaluable even when optional external providers are not
configured.

## Problem Statement

Investment teams often work across fragmented tools: one system for portfolio
analytics, another for research, another for approvals, and separate ad hoc
LLM experiments with weak auditability. That creates four problems:

1. market, portfolio, policy, macro, SEC, and internal research context is not
   assembled in one place;
2. agentic recommendations are difficult to inspect and hard to trust;
3. human approval workflows are bolted on late instead of designed in;
4. demos and evaluations break when live APIs or keys are unavailable.

AlphaLens addresses this by providing a single interface where an agent can
investigate an investment question, show evidence and tool usage, generate a
decision artifact, route it through human approval when needed, and remain
stable in offline or deterministic demo mode.

## Target Users

- Portfolio managers reviewing positions, risks, and trade ideas
- Research analysts producing memos and scenario analysis
- Risk and compliance reviewers validating rationale and approvals
- Reviewers and evaluators assessing an AI-native fintech workflow end to end

## Key Features

- Portfolio dashboard with risk, alerts, holdings, and usage visibility
- Agent chat that investigates through portfolio, policy, market, news, macro,
  SEC, and retrieval tools
- Decision cards with recommendation, confidence, evidence, and approval state
- Human-in-the-loop approval queue with audit-friendly status tracking
- Structured memo generation from chat context
- Deterministic scenario simulation for what-if analysis
- Usage and cost dashboard for LLM/tool activity and feedback loops
- Deterministic fallback mode so the app remains demoable without live APIs

## Architecture Overview

AlphaLens is split into three surfaces:

- `frontend/`: Next.js App Router application for dashboards, chat, reports,
  approvals, settings, and reviewer demo flow
- `backend/`: FastAPI service exposing typed endpoints for portfolio, chat,
  approvals, reports, scenarios, usage, memory, speech, and health
- infrastructure: Dockerized Postgres, Redis, and Qdrant, with optional
  external providers for LLM, market data, search/news, macro data, and SEC

See the full architecture package:

- [docs/architecture.md](docs/architecture.md)
- [docs/decisions.md](docs/decisions.md)
- [docs/demo_script.md](docs/demo_script.md)
- [docs/validation_report.md](docs/validation_report.md)
- [docs/setup.md](docs/setup.md)

## Tech Stack

### Frontend

- Next.js 14 App Router
- React 18
- TypeScript
- Tailwind CSS
- Radix UI primitives

### Backend

- FastAPI
- Pydantic v2
- LangGraph
- SQLAlchemy
- Redis client
- Qdrant client
- OpenAI SDK

### Infrastructure

- Docker Compose
- Postgres 16
- Redis 7
- Qdrant

## Repository Layout

```text
AlphaLens-AI/
  backend/      FastAPI service, agent orchestration, tools, tests
  frontend/     Next.js dashboard and reviewer-facing UI
  docs/         Architecture, ADRs, demo script, validation report
  data/         Synthetic fixtures and knowledge sources
  docker-compose.yml
  .env.example
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/)
- [pnpm](https://pnpm.io/) 9+ for normal frontend workflows
- Docker Desktop / Docker Compose

### 1. Configure environment

```bash
cp .env.example .env
```

Optional for local frontend-only development:

```bash
cd frontend
cp .env.local.example .env.local
```

### 2. Start infrastructure services

```bash
docker compose up -d postgres redis qdrant
```

### 3. Run the backend

```bash
cd backend
uv sync --extra dev
uv run uvicorn alphalens.api.main:app --reload
```

Backend endpoints:

- API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 4. Run the frontend

```bash
cd frontend
pnpm install
pnpm dev
```

Frontend app:

- App: `http://localhost:3000`

## Docker Instructions

To run the full stack in containers:

```bash
docker compose up --build
```

This launches:

- `postgres`
- `redis`
- `qdrant`
- `backend`
- `frontend`

Useful commands:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose down
```

The frontend uses `/api/backend` as a same-origin proxy path and routes
server-side traffic to `BACKEND_INTERNAL_URL`.

## Environment Variables

Key variables are documented in `.env.example`. The most important groups are:

### Core app

- `APP_ENV`
- `LOG_LEVEL`
- `APP_VERSION`

### Persistence and infrastructure

- `DATABASE_URL`
- `APP_DATABASE_URL`
- `PERSISTENCE_BACKEND`
- `REDIS_URL`
- `QDRANT_URL`

### Frontend routing

- `NEXT_PUBLIC_API_URL`
- `BACKEND_INTERNAL_URL`

### Agent and provider configuration

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TEMPERATURE`
- `OPENAI_TOP_P`
- `LLM_ENABLED`
- `ANTHROPIC_API_KEY`

### Optional provider selection

- `MARKET_DATA_PROVIDER`
- `SEARCH_PROVIDER`
- `MACRO_DATA_PROVIDER`
- `SEC_PROVIDER`

### Demo-stability and supporting services

- `CACHE_ENABLED`
- `CACHE_TTL_SECONDS`
- `MEMORY_ENABLED`
- `MEMORY_BACKEND`
- `MEMORY_TTL_SECONDS`
- `SPEECH_ENABLED`
- `DEFAULT_RESPONSE_LANGUAGE`
- `SPEECH_MAX_UPLOAD_BYTES`

By default, most optional providers can run in `fallback` mode so reviewers can
evaluate deterministic product behavior without external network dependencies.

## Demo Flow

Recommended reviewer flow:

1. Open the dashboard and frame AlphaLens as an investment copilot with
   portfolio, approvals, reports, scenarios, usage, and settings.
2. Ask a portfolio or investment question in chat.
3. Show the resulting decision card, evidence, and tool usage.
4. Navigate to approvals to demonstrate human review.
5. Generate or open a memo from the decision context.
6. Run a deterministic scenario simulation.
7. Open usage to show cost, event, and feedback tracking.
8. End in settings to show providers, tools, and deterministic fallback mode.

For a timed walkthrough with exact prompts, use
[docs/demo_script.md](docs/demo_script.md).

## Testing Instructions

### Backend

```bash
cd backend
uv run pytest
```

Optional backend linting:

```bash
uv run ruff check .
uv run mypy src
```

### Frontend

```bash
cd frontend
pnpm lint
pnpm build
```

If package-manager shims are unavailable in the shell, the local binaries can be
run directly:

```bash
node ./node_modules/eslint/bin/eslint.js src --ext .js,.jsx,.ts,.tsx
node ./node_modules/next/dist/bin/next build
```

### Docker / healthchecks

```bash
docker compose up --build
docker compose ps
```

## Limitations

- AlphaLens does not execute real trades.
- Portfolio and some investigation data are synthetic or deterministic.
- Deterministic fallbacks are intentionally used for demo and offline mode.
- External APIs are optional and may be disabled entirely.
- Some MVP services remain in-memory unless explicitly configured otherwise.
- The project is not financial advice and should not be used for real
  investment decisions.

## Future Roadmap

- Durable persistence for more services beyond approvals
- Stronger investigation timelines and audit replay
- Real document ingestion and richer RAG workflows
- Additional market/news/provider adapters
- Authentication, user scoping, and access control
- Production-grade observability and evaluation workflows
- Deeper policy engine and approval routing rules
- Broker/execution integrations behind stricter guardrails

## Submission Notes

AlphaLens is optimized for reviewer evaluation:

- the backend and frontend expose typed, inspectable contracts;
- the UI is demo-ready and stable in deterministic mode;
- human approval is a first-class workflow;
- limitations and tradeoffs are explicitly documented;
- validation artifacts are included in `docs/validation_report.md`.
