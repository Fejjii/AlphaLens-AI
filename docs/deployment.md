# Deployment

AlphaLens AI is designed for a split deployment:

- frontend on Vercel
- backend on Render or Railway
- Postgres on a managed Postgres service
- Redis on managed Redis or Upstash
- Qdrant on Qdrant Cloud or a Docker-managed instance

The app keeps deterministic fallback behavior, so reviewers can still exercise
the product even when optional provider keys are omitted.

## Recommended topology

Use a public frontend URL and a separate public backend URL. The frontend should
call the backend through the Next.js proxy route at `/api/backend/*` so browser
requests stay same-origin. The proxy then forwards to the backend using
`BACKEND_INTERNAL_URL`.

For local Docker the internal target is `http://backend:8000`. In Vercel
production it should be the public backend origin, for example:

```text
https://alphalens-backend.onrender.com
```

If you prefer direct client requests, set `NEXT_PUBLIC_API_URL` to the public
backend URL and bypass the proxy, but the proxy route is the safer default
because it preserves same-origin browser calls and cookies.

## Backend deployment

The backend is configured to read `PORT` from the environment via
`python -m alphalens.api.serve`.

### Backend env vars

Required or strongly recommended:

- `APP_ENV=prod`
- `APP_VERSION`
- `LOG_LEVEL`
- `APP_DATABASE_URL` for production persistence
- `DATABASE_URL` if the platform uses the same URL for startup and runtime
- `REDIS_URL` for cache, memory, and rate-limit backends
- `RATE_LIMIT_REDIS_URL` if you want rate limiting shared across replicas
- `QDRANT_URL`
- `QDRANT_API_KEY` if your Qdrant deployment requires authentication
- `CORS_ALLOW_ORIGINS` including the deployed frontend origin

Optional but commonly set:

- `PERSISTENCE_BACKEND=postgres`
- `MEMORY_BACKEND=redis`
- `RATE_LIMIT_BACKEND=redis`
- `MARKET_DATA_PROVIDER=fallback`
- `SEARCH_PROVIDER=fallback`
- `MACRO_DATA_PROVIDER=fallback`
- `SEC_PROVIDER=fallback`
- `LLM_ENABLED=false` for deterministic offline deployments
- `SPEECH_ENABLED=false` if you do not want speech uploads in production

### Render/Railway notes

`render.yaml` provides a minimal Render blueprint for both services. For Railway,
the same build and start commands apply:

- backend build: `uv sync --extra dev`
- backend start: `uv run python -m alphalens.api.serve`

If the platform injects a different port, the backend will honor `PORT`
automatically.

### CORS checklist

Add the deployed frontend origin to `CORS_ALLOW_ORIGINS`, for example:

```text
https://alphalens-frontend.vercel.app
```

Keep local development origins too if you still need them:

```text
http://localhost:3000
```

## Frontend deployment

The frontend is ready for Vercel with no custom runtime config required.

### Frontend env vars

- `NEXT_PUBLIC_API_URL=/api/backend` recommended for browser and server code
- `BACKEND_INTERNAL_URL` set to the public backend URL in Vercel production
- `NODE_ENV=production`
- `NEXT_STANDALONE=true` when building Docker images that copy `.next/standalone`

The frontend proxy route in `frontend/src/app/api/backend/[...path]/route.ts`
forwards requests to `BACKEND_INTERNAL_URL`. That means Vercel does not need a
private network link to the backend.

If you want direct public calls from the browser, set `NEXT_PUBLIC_API_URL` to
the backend origin. That is simpler, but you lose same-origin proxying and may
need tighter CORS handling.

Local Windows note: `pnpm build` defaults to non-standalone output to avoid
filesystem symlink `EPERM` issues. Container builds set `NEXT_STANDALONE=true`
to preserve standalone runtime packaging.

## Managed services

### Postgres

Use a managed Postgres database and copy the connection string into
`APP_DATABASE_URL`. If the platform also supplies `DATABASE_URL`, keep the two
values aligned.

### Redis

Use managed Redis or Upstash and set `REDIS_URL`. If rate limiting must work
across multiple backend instances, also set `RATE_LIMIT_REDIS_URL` to the same
or a dedicated Redis endpoint and set `RATE_LIMIT_BACKEND=redis`.

### Qdrant

Use Qdrant Cloud or a Docker-managed Qdrant instance.

- set `QDRANT_URL` to the cluster URL or internal service URL
- set `QDRANT_API_KEY` only if the deployment requires it

## Secrets checklist

Do not commit secrets to the repository. Store them only in the hosting
platform's secret manager.

Backend secrets:

- `APP_DATABASE_URL`
- `DATABASE_URL`
- `REDIS_URL`
- `RATE_LIMIT_REDIS_URL`
- `QDRANT_API_KEY`
- `OPENAI_API_KEY`
- `SERPER_API_KEY`
- `FRED_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `LANGCHAIN_API_KEY`

Frontend secrets:

- `BACKEND_INTERNAL_URL`

## Smoke checklist

Run these checks after deployment:

1. `GET /health` on the backend returns `ok`
2. The frontend homepage loads in the browser
3. The `/api/backend/*` proxy reaches the backend
4. Register and login succeed
5. Chat requests return a response
6. Usage summary loads
7. Reports and scenarios pages load and submit successfully
8. Docker Compose still works locally as an alternative deployment path

## Fallback and offline mode

AlphaLens intentionally supports fallback providers so the application remains
demoable without external API credentials.

- market data falls back when Alpha Vantage is not configured
- search falls back when Serper is not configured
- macro data falls back when FRED is not configured
- SEC lookups fall back when `SEC_PROVIDER=fallback`
- LLM and speech can be disabled for stable production and demo runs

This keeps deployment verification deterministic while still allowing live
providers to be enabled later.
