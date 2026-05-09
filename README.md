# AlphaLens AI

AlphaLens AI is an agentic investment intelligence and portfolio decision support platform.

## Project Highlights

- Agent Chat with routing for `app_help`, `out_of_scope`, `clarification`, and `investment_decision`
- Portfolio analysis, policy/risk checks, scenario analysis, and context-specific memo generation
- Hybrid RAG over internal and uploaded docs with clean executive responses and source traceability
- Market/news/macro/SEC context with deterministic fallback behavior for demo reliability
- Human-in-the-loop approvals, persisted investigations timeline, reports, feedback analytics, and usage/cost tracking
- Authentication, plans/quotas, speech and multilingual support, observability/tracing, and Dockerized local stack

## Core Features

- Agent Chat
- Portfolio analysis
- Policy and risk checks
- Hybrid RAG over internal documents
- Market/news context
- Macro context
- SEC filings context
- Scenario analysis
- Human-in-the-loop approvals
- Investigations timeline
- Context-specific memo generation
- Feedback analytics
- Usage/cost tracking
- Authentication and plans
- Speech/multilingual support
- Observability and tracing
- Dockerized local stack

## Stack

### Backend

- FastAPI
- Pydantic v2
- LangGraph
- LangChain Core
- OpenAI
- Qdrant
- Redis
- Postgres
- SQLAlchemy
- pytest
- Docker

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn-style/Radix-based component patterns

### Infra

- Docker Compose
- GitHub Actions
- Postgres
- Redis
- Qdrant

## Quickstart

### Docker

```bash
docker compose up --build
```

### Local backend/frontend

```bash
cd backend && uv sync && uv run pytest
cd frontend && pnpm install && pnpm dev
```

## Environment Variables

Use `.env.example` and `.env.local.example` as templates. Never commit secrets.

### Required for live providers

- `OPENAI_API_KEY`

### Optional providers and observability

- `SERPER_API_KEY`
- `FRED_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `LANGCHAIN_TRACING_V2`
- `LANGCHAIN_API_KEY`
- `LANGCHAIN_PROJECT`

### Runtime and persistence

- `PERSISTENCE_BACKEND`
- `APP_DATABASE_URL`
- `REDIS_URL`
- `QDRANT_URL`

### Frontend runtime flags

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_DEBUG_UI`

## Demo

Use the 5-7 minute reviewer script in [docs/demo_script.md](docs/demo_script.md).

## Architecture and Technical Docs

- [docs/architecture.md](docs/architecture.md)
- [docs/agent_workflow.md](docs/agent_workflow.md)
- [docs/data_architecture.md](docs/data_architecture.md)
- [docs/rag_system.md](docs/rag_system.md)
- [docs/security_compliance.md](docs/security_compliance.md)
- [docs/evaluation.md](docs/evaluation.md)
- [docs/deployment.md](docs/deployment.md)
- [docs/repo_map.md](docs/repo_map.md)
- [docs/limitations_roadmap.md](docs/limitations_roadmap.md)

## Limitations

- No real trading or broker execution
- Not financial advice
- Fallback providers are used in demo mode when live keys/providers are unavailable
- Scenario simulation in chat is first-order unless using the Scenarios service flow
- Dev/test report schema guard is in place; Alembic migrations are recommended for production
- Billing/admin capabilities are roadmap items
