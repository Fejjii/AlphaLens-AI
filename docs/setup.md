# Setup

## Prerequisites

- Python 3.11+
- Node.js 20 LTS
- [pnpm](https://pnpm.io/) 9+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker + Docker Compose

## Clone and configure

```bash
git clone <repo> alphalens
cd alphalens
cp .env.example .env
```

## Start data plane

```bash
docker compose up -d postgres redis qdrant
```

Verify:

```bash
docker compose ps
```

## Backend

```bash
cd backend
uv sync
uv run uvicorn alphalens.api.main:app --reload
```

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs

Run tests:

```bash
uv run pytest
```

Windows (PowerShell) quick start for backend tests:

```powershell
cd backend
uv sync
uv run pytest
```

Speech endpoint smoke test (multipart upload):

```bash
curl -X POST http://localhost:8000/speech/transcribe \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@sample.webm;type=audio/webm"
```

Windows PowerShell variant:

```powershell
curl.exe -X POST http://localhost:8000/speech/transcribe ^
  -H "Authorization: Bearer <access_token>" ^
  -F "file=@sample.webm;type=audio/webm"
```

Chrome live microphone recordings are typically uploaded as
`audio/webm` or `audio/webm;codecs=opus`.

### Microphone transcription (OpenAI)

Real speech-to-text uses OpenAI and requires `OPENAI_API_KEY` in the backend environment.

1. Add `OPENAI_API_KEY=...` to the project `.env` file in the repo root (the same file Docker Compose loads).
2. Restart containers so the backend process picks up the variable: `docker compose down` then `docker compose up --build`.
3. Verify the API (requires an authenticated session): `GET /speech/capabilities` should report `provider_mode: "real"`, `openai_key_configured: true`, and `microphone_transcription_available: true`.

```bash
curl -s http://localhost:8000/speech/capabilities -H "Authorization: Bearer <access_token>"
```

Without a key, `/speech/transcribe` returns an empty `transcript`, a separate `demo_transcript` for optional demos, and `fallback_used: true`. Inspect server-side traces in development with:

```bash
docker compose logs backend | findstr speech
```

On Unix shells, use `grep speech` instead of `findstr`.

The backend startup path now creates SQLAlchemy tables for approvals, feedback,
reports, scenarios, usage events, users, and conversation memory when Postgres
is enabled. For long-lived production environments, add Alembic migrations once
the schema starts evolving beyond the MVP.

Lint and format:

```bash
uv run ruff check .
uv run ruff format .
```

## Frontend

```bash
cd frontend
cp .env.local.example .env.local
pnpm install
pnpm dev
```

App: http://localhost:3000.

For local Windows builds, `pnpm build` runs without Next.js standalone output
by default to avoid symlink permission issues. Docker/production image builds
explicitly set `NEXT_STANDALONE=true` so `.next/standalone` is still generated.

## Full stack via Docker

```bash
docker compose up --build
```

This builds and runs `backend` and `frontend` alongside the data plane.

Docker persistence behavior for demo data:

- `docker compose down` keeps named volumes, so Postgres users and refresh tokens stay available.
- `docker compose down -v` removes named volumes and deletes demo Postgres data.
- Use `docker compose down -v` only when you intentionally need a clean reset.

## Common issues

- **Port already in use** — change the published port in
  `docker-compose.yml` or stop the conflicting process.
- **Backend cannot reach Postgres/Redis/Qdrant** — confirm the relevant
  service is healthy via `docker compose ps`. The default `DATABASE_URL`
  in `.env.example` targets the in-network hostname `postgres`.
- **Frontend shows mock data** — the API client falls back to mocks when
  the backend is unreachable. Confirm `NEXT_PUBLIC_API_URL` and that the
  backend is running.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `dev` / `staging` / `prod` / `test` |
| `LOG_LEVEL` | Backend log level |
| `DATABASE_URL` / `APP_DATABASE_URL` | Runtime DB URL / local psycopg URL |
| `PERSISTENCE_BACKEND` | `in_memory` or `postgres` workflow persistence |
| `RATE_LIMIT_BACKEND` / `RATE_LIMIT_REDIS_URL` | In-memory or Redis-backed rate limiting for multi-instance deployments |
| `RATE_LIMIT_*` | Per-route thresholds for auth, chat, speech, reports, scenarios, and feedback |
| `REDIS_URL` | Redis URL |
| `QDRANT_URL` | Qdrant base URL |
| `KNOWLEDGE_BASE_PATH` / `RAG_COLLECTION` / `RAG_EMBEDDING_DIM` | RAG knowledge store configuration |
| `NEXT_PUBLIC_API_URL` | Public frontend API base (`/api/backend` recommended) |
| `BACKEND_INTERNAL_URL` | Server-side proxy target (`http://localhost:8000` local, `http://backend:8000` in Docker) |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `LLM_ENABLED` | LLM provider credentials and toggle |
| `SPEECH_ENABLED` / `SPEECH_MAX_UPLOAD_BYTES` / `DEFAULT_RESPONSE_LANGUAGE` | Speech endpoint and response language behavior |
| `MARKET_DATA_PROVIDER` / `SEARCH_PROVIDER` / `MACRO_DATA_PROVIDER` / `SEC_PROVIDER` | External integration provider selection (`fallback` supported for deterministic offline mode) |
| `LANGCHAIN_TRACING_V2` / `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT` | Optional LangSmith tracing |

For Docker runtime, the frontend uses a Next.js proxy route (`/api/backend/*`) so browser requests stay same-origin while the frontend container reaches backend over the Docker network (`http://backend:8000`).

In production, set `RATE_LIMIT_BACKEND=redis` and point `RATE_LIMIT_REDIS_URL` at a shared Redis instance so counters are enforced across all API replicas. Keep `RATE_LIMIT_BACKEND=memory` for local and test runs when you want deterministic single-process behavior.
