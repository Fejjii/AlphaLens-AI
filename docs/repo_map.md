# Repository Map

## Major Directories

- `backend/src/alphalens/api`: FastAPI routers, dependency wiring, middleware, and entrypoint composition
- `backend/src/alphalens/services`: Domain services (chat, reports, investigations, approvals, scenarios, auth, usage)
- `backend/src/alphalens/agents`: LangGraph graph, nodes, and state contracts
- `backend/src/alphalens/tools`: Agent tool implementations and registry-facing contracts
- `backend/src/alphalens/repositories`: Persistence interfaces/implementations for user-scoped entities
- `backend/src/alphalens/integrations`: External providers and fallback adapters
- `backend/src/alphalens/memory`: Conversation memory backends (in-memory, Redis, SQLAlchemy-backed options)
- `backend/src/alphalens/schemas`: Pydantic request/response/domain schemas
- `backend/tests`: Backend test suite (routing, tools, RAG, auth, approvals, reports, investigations, speech)
- `frontend/src/app`: Next.js App Router pages and route segments
- `frontend/src/components`: Shared UI components (chat, layout, cards, controls)
- `frontend/src/lib`: API clients, formatting helpers, memo payload utilities, runtime helpers
- `frontend/src/types`: Shared frontend TypeScript domain and API types
- `docs`: Architecture, workflow, deployment, security, evaluation, and demo documentation
- `data/knowledge_base`: Seeded internal knowledge base markdown corpus
- `.github/workflows`: CI pipelines for backend, frontend, Docker, and security checks

## Key Infrastructure Files

- `docker-compose.yml`: Local multi-service stack
- `render.yaml`: Managed deployment reference

## Useful Commands

```bash
docker compose up --build
cd backend && uv run pytest
cd frontend && pnpm lint && pnpm build
git status
git diff --stat
git check-ignore .env
git ls-files .env
```
