# AlphaLens AI

AlphaLens AI is an agentic investment intelligence and portfolio decision support platform built for production-style evaluation.

## 1) Product Problem and Target Users

Investment teams typically split workflow across disconnected tools for portfolio analytics, policy checks, research, and approvals. That creates weak traceability, inconsistent decision quality, and limited governance over AI-generated recommendations.

AlphaLens AI unifies those workflows for:
- portfolio managers reviewing risk and position decisions;
- research analysts generating investment memos and scenarios;
- compliance and risk reviewers enforcing policy guardrails;
- technical reviewers evaluating an end-to-end AI engineering system.

## 2) Key Features

- FastAPI + Next.js full-stack product with authenticated user workflows
- LangGraph agent orchestration (`interpret -> gather -> synthesize -> decide`)
- Hybrid RAG over internal and uploaded documents using Qdrant
- Market/news/macro/SEC tooling with fallback provider architecture
- Human-in-the-loop (HITL) approvals for sensitive recommendations
- Reports, scenario simulations, feedback capture, and usage/cost tracking
- Plan quotas, JWT auth + refresh token support, and rate limiting
- Deterministic fallback mode for reliable local demos without external APIs

## 3) Architecture Overview

At a high level:
- browser users interact with a Next.js frontend;
- frontend calls FastAPI backend (`/api/backend` proxy pattern supported);
- backend orchestrates LangGraph, tools, provider adapters, and storage;
- Postgres, Redis, and Qdrant provide persistence, caching, and retrieval.

Detailed architecture diagrams are in [docs/architecture.md](docs/architecture.md).

## 4) AI Agent Workflow

AlphaLens uses a multi-step agent workflow, not a single prompt-response chatbot:
- interpret user intent and classify task;
- gather evidence via portfolio tools, policy checks, market/news/macro/SEC, and RAG;
- synthesize evidence with explicit limitations;
- decide recommendation with compliance metadata and approval gating.

Detailed flow and sequence diagram: [docs/agent_workflow.md](docs/agent_workflow.md).

## 5) Hybrid RAG Overview

RAG combines internal knowledge base documents with uploaded user documents:
- ingestion chunks markdown/text sources and stores embeddings in Qdrant;
- retrieval provides relevant evidence snippets for response grounding;
- response payload includes source references for UI display.

Detailed RAG design: [docs/rag_system.md](docs/rag_system.md).

## 6) Data and Storage Architecture

- `Postgres`: users, refresh tokens, approvals, feedback, reports, scenarios, usage events, conversation memory
- `Redis`: cache, rate limiting, and runtime fallback support where configured
- `Qdrant`: document vectors and chunk metadata for hybrid retrieval
- local files: seeded synthetic data and seeded knowledge base content

Detailed data map: [docs/data_architecture.md](docs/data_architecture.md).

## 7) Security, Compliance, and HITL

- JWT access + refresh token auth model
- protected API routes and plan quota enforcement
- upload validation and rate limiting
- policy guardrails with approval queue for sensitive actions
- compliance metadata included in agent responses

Security and compliance details: [docs/security_compliance.md](docs/security_compliance.md).

## 8) Tech Stack

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** FastAPI, Pydantic, LangGraph, SQLAlchemy
- **AI/RAG:** OpenAI, Qdrant, structured tool orchestration
- **Data/Infra:** Postgres, Redis, Docker Compose
- **CI/CD:** GitHub Actions workflows for backend, frontend, docker, security

## 9) Quick Start With Docker

```bash
cp .env.example .env
docker compose up --build
```

Then open:
- frontend: `http://localhost:3000`
- backend health: `http://localhost:8000/health`
- backend docs: `http://localhost:8000/docs`

## 10) Local Development Setup

Backend:
```bash
cd backend
uv sync --extra dev
uv run uvicorn alphalens.api.main:app --reload
```

Frontend:
```bash
cd frontend
pnpm install
pnpm dev
```

## 11) Environment Variables

Use `.env.example` as the source of truth. Key groups:
- app/runtime: `APP_ENV`, `LOG_LEVEL`, `APP_VERSION`
- data services: `APP_DATABASE_URL`, `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`
- auth/security: JWT secret and token settings
- providers: `OPENAI_API_KEY`, `SERPER_API_KEY`, `FRED_API_KEY`, `ALPHA_VANTAGE_API_KEY`
- routing: `NEXT_PUBLIC_API_URL`, `BACKEND_INTERNAL_URL`
- feature flags: provider selection, fallback modes, speech, memory, cache

## 12) Validation Commands

Backend:
```bash
cd backend
uv sync
uv run pytest
```

Frontend:
```bash
cd frontend
pnpm lint
pnpm build
```

Repository checks:
```bash
git status
git check-ignore .env
git ls-files .env
```

## 13) Demo Flow

Use the short reviewer flow in [docs/demo_script.md](docs/demo_script.md):
1. product framing and dashboard
2. runtime status and fallback explanation
3. knowledge base and RAG
4. agent chat + approval workflow
5. reports and scenarios
6. usage and feedback

## 14) Screenshots

No `screenshots/` directory is currently included in this repository. Screenshot sections can be added later for:
- dashboard;
- chat decision card;
- approval queue;
- reports/scenarios;
- usage/cost view.

## 15) Limitations

- AlphaLens does **not** execute real broker trades.
- The platform is **not** financial advice.
- Demo portfolio and seeded content are synthetic unless real providers are configured.
- External providers may be unavailable; fallback providers are intentionally included for reliable local demos.
- Some production controls (immutable audit, RBAC maturity, formal legal sign-off) are roadmap items.

## 16) Production Roadmap

See [docs/limitations_roadmap.md](docs/limitations_roadmap.md) for the full roadmap, including:
- stronger compliance controls and audit capabilities;
- enhanced RAG quality/evaluation pipeline;
- richer market/fundamentals ingestion;
- SaaS hardening (RBAC, 2FA, billing, observability).

## 17) Repository Structure

See [docs/repo_map.md](docs/repo_map.md) for full structure and command map.

Top-level:
```text
backend/      FastAPI APIs, agent orchestration, tools, services, tests
frontend/     Next.js application and UI components
data/         Synthetic seed data and knowledge base files
docs/         Architecture, deployment, evaluation, demo, roadmap
.github/      CI workflows
docker-compose.yml
render.yaml
```

## 18) CI/CD Overview

GitHub Actions workflows validate:
- backend tests and quality checks;
- frontend lint/build;
- Docker build and compose validation;
- security checks including secret scanning.

Workflow details: `.github/workflows`.
