# Repository Map

This map explains where core functionality lives and which commands are most important for validation and delivery.

## Core Directories

### `backend/src/alphalens/api`

FastAPI routers, dependencies, API wiring, and service entrypoints.

### `backend/src/alphalens/services`

Business orchestration layer for chat, approvals, reports, scenarios, usage, and policy-aware workflows.

### `backend/src/alphalens/agents`

LangGraph orchestration nodes and agent state management.

### `backend/src/alphalens/tools`

Tool layer used by the agent (portfolio, risk, policy, market, macro, SEC, RAG helpers).

### `backend/src/alphalens/integrations`

External provider clients and fallback adapters (OpenAI, Serper, FRED, Alpha Vantage, SEC, speech).

### `backend/src/alphalens/repositories`

Persistence abstractions for users, tokens, approvals, feedback, reports, scenarios, usage, and memory.

### `backend/src/alphalens/schemas`

Pydantic contracts for request/response payloads and typed domain schemas.

### `backend/tests`

Backend test suite for APIs, orchestration, RAG, auth, quotas, and persistence behavior.

### `frontend/src/app`

Next.js App Router pages (dashboard, chat, approvals, reports, scenarios, usage, settings, auth).

### `frontend/src/components`

Reusable UI components for chat, layout, cards, badges, and shared visuals.

### `frontend/src/lib`

Frontend API clients, helpers, event utilities, and fallback handling.

### `frontend/src/types`

TypeScript API/domain type definitions aligned with backend contracts.

### `data`

Synthetic demo data and knowledge base source files.

### `docs`

Architecture, setup, deployment, evaluation, demo script, and roadmap documentation.

### `.github/workflows`

CI workflows for backend, frontend, Docker, and security checks.

### Infrastructure files

- `docker-compose.yml`: local multi-service runtime (frontend, backend, Postgres, Redis, Qdrant)
- `render.yaml`: deployment blueprint reference for Render

## Important Commands

### Backend

```bash
cd backend
uv sync
uv run pytest
```

### Frontend

```bash
cd frontend
pnpm lint
pnpm build
```

### Repo checks

```bash
git status
git check-ignore .env
git ls-files .env
```

### Local full stack

```bash
docker compose up --build
```
