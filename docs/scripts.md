# Scripts and Commands

This guide documents the practical command set for local development, CI, Docker
operations, validation, and final delivery.

## 1) Backend Commands

Run from repo root unless noted.

```bash
cd backend
uv sync --extra dev
```
- Installs backend runtime + dev dependencies into the uv environment.

```bash
cd backend
uv run pytest
```
- Runs backend tests.

```bash
cd backend
uv run ruff check .
```
- Runs backend lint checks.

```bash
cd backend
uv run mypy src
```
- Runs strict type checks (configured in `pyproject.toml`).

```bash
cd backend
uv run uvicorn alphalens.api.main:app --reload
```
- Runs backend locally in reload mode.

### Backend environment variables (most used)

- `APP_ENV`, `LOG_LEVEL`, `APP_VERSION`
- `DATABASE_URL`, `APP_DATABASE_URL`, `PERSISTENCE_BACKEND`
- `REDIS_URL`, `RATE_LIMIT_BACKEND`, `RATE_LIMIT_REDIS_URL`
- `QDRANT_URL`, `QDRANT_API_KEY`
- `KNOWLEDGE_BASE_PATH`, `RAG_COLLECTION`, `RAG_EMBEDDING_DIM`
- `OPENAI_API_KEY`, `LLM_ENABLED`, `SPEECH_ENABLED`
- `MARKET_DATA_PROVIDER`, `SEARCH_PROVIDER`, `MACRO_DATA_PROVIDER`, `SEC_PROVIDER`

## 2) Frontend Commands

```bash
cd frontend
pnpm install
```
- Installs frontend dependencies.

```bash
cd frontend
pnpm dev
```
- Runs frontend local dev server.

```bash
cd frontend
pnpm lint
```
- Runs ESLint.

```bash
cd frontend
pnpm build
```
- Runs production build validation.

### Frontend environment variables (most used)

- `NEXT_PUBLIC_API_URL` (recommended `/api/backend`)
- `BACKEND_INTERNAL_URL` (proxy target for server route)
- `NEXT_STANDALONE` (`true` for Docker standalone packaging builds)
- `NODE_ENV`

## 3) Docker Commands

```bash
docker compose config
```
- Validates compose syntax and resolved runtime config.

```bash
docker compose up --build
```
- Builds and starts full stack in foreground.

```bash
docker compose up -d --build
```
- Builds and starts full stack detached.

```bash
docker compose ps
```
- Shows service health and running status.

```bash
docker compose logs -f backend
docker compose logs -f frontend
```
- Streams service logs.

```bash
docker compose down
```
- Stops and removes running compose services.

## 4) CI/CD Workflows

Defined under `.github/workflows`:

- `backend-ci.yml`
  - Installs `uv`
  - Syncs backend deps
  - Runs `pytest`, `ruff`, `mypy`
  - Uses deterministic fallback-safe env defaults

- `frontend-ci.yml`
  - Sets up Node + pnpm
  - Runs `pnpm lint` and `pnpm build`
  - Uses safe API defaults without requiring live backend

- `docker-ci.yml`
  - Runs `docker compose config`
  - Builds backend and frontend images

- `security-ci.yml`
  - Runs dependency review on PRs
  - Runs Gitleaks secret scanning

## 5) Final Validation Checklist Commands

```bash
# Backend
cd backend
uv run pytest

# Frontend
cd ../frontend
pnpm lint
pnpm build

# Docker
cd ..
docker compose config
docker compose up -d --build
docker compose ps
```

Smoke endpoints:

- `GET http://localhost:8000/health`
- `POST http://localhost:8000/auth/register`
- `POST http://localhost:8000/auth/login`
- `POST http://localhost:8000/chat`
- `GET http://localhost:8000/usage/summary`
- `GET http://localhost:8000/reports/summary`
- `POST http://localhost:8000/scenarios`
- `GET http://localhost:8000/scenarios/summary`
- `GET http://localhost:3000`

Cleanup:

```bash
docker compose down
```

## 6) Git Delivery Commands

```bash
git status
git add <files>
git commit -m "final: document and productionize AlphaLens AI platform"
git push origin main
git push turing main
```

If the default branch is `master`, push `master` instead of `main`.

If `turing` remote is missing:

```bash
git remote add turing https://github.com/TuringCollegeSubmissions/sfejji-AE.3.5.git
```
