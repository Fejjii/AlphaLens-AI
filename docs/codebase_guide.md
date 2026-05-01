# Codebase Guide

This guide maps the major directories in AlphaLens AI and explains how the
backend, frontend, data, docs, and CI layers connect.

## 1) `backend/src/alphalens/api`

API transport and application wiring:
- FastAPI app factory and startup/lifespan handling
- routers for auth, agent/chat, approvals, reports, scenarios, usage, memory
- dependency providers (`deps.py`)
- middleware and request/response cross-cutting concerns
- production entrypoint (`serve.py`)

## 2) `backend/src/alphalens/services`

Business orchestration layer:
- chat/agent execution and workflow coordination
- approvals, reports, scenarios, feedback, usage
- auth and plan services
- compliance checks
- provider selection and fallback routing

## 3) `backend/src/alphalens/repositories`

Persistence abstraction:
- repository interfaces and implementations
- in-memory repositories for local/test deterministic behavior
- SQLAlchemy-backed repositories for Postgres-ready persistence
- user-scoped read/write patterns

## 4) `backend/src/alphalens/integrations`

External provider adapters:
- LLM, market, search/news, macro, SEC, speech integrations
- normalized adapter interfaces
- fallback clients to preserve deterministic behavior

## 5) `backend/src/alphalens/tools`

Agent tool registry and tool implementations:
- portfolio/risk/market/macro/SEC/RAG tools
- tool schema/metadata exposed to agent layer
- execution wrappers and typed results

## 6) `backend/src/alphalens/rag`

Retrieval stack:
- markdown ingestion/chunking
- embeddings
- Qdrant retriever/index interactions
- retrieval outputs fed into agent evidence/citations

## 7) `backend/src/alphalens/schemas`

Typed API and domain contracts:
- Pydantic request/response models
- chat, approvals, reports, scenarios, feedback, usage, auth, plans
- shared enums/unions for strict cross-layer consistency

## 8) `frontend/src/app`

Next.js App Router surfaces:
- dashboard/home
- chat/agent interactions
- approvals, reports, scenarios
- usage and settings
- auth pages (`/login`, `/register`)
- proxy route (`/api/backend/[...path]`) for server-side forwarding

## 9) `frontend/src/components`

Reusable UI system:
- layout shell and navigation
- auth wrappers/guards
- chat panels/cards/tables
- status badges and shared UI primitives

## 10) `frontend/src/lib`

Frontend service helpers:
- API client and fallback handling
- server API helpers
- auth helpers
- mock data for deterministic UX in offline/unavailable states
- utility helpers

## 11) `frontend/src/types`

TypeScript contracts:
- frontend API payload types
- typed alignment with backend schema contracts
- strict unions for statuses/recommendations/events

## 12) `data`

Shared synthetic and knowledge inputs:
- `data/synthetic` for portfolio and scenario test/demo fixtures
- `data/knowledge_base` markdown sources for RAG ingestion
- packaged into backend Docker image for runtime parity

## 13) `docs`

Engineering and reviewer package:
- architecture, decisions, setup, scripts, deployment
- codebase guide
- demo script and validation report

## 14) `.github/workflows`

Automation and CI/CD:
- backend quality gates (tests/lint/types)
- frontend lint/build validation
- docker config and image build checks
- lightweight security checks (dependency review + secret scanning)

## How These Layers Connect

1. Frontend calls backend via proxy/direct API.
2. Backend routes request to services.
3. Services invoke tools, repositories, RAG, and integrations.
4. Integrations select real provider or deterministic fallback.
5. Repositories persist user-scoped entities in memory or Postgres.
6. Usage/feedback events are recorded for observability and quota tracking.
