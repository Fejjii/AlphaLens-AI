# Validation Report

This report summarizes the final submission validation status for AlphaLens AI.

## Summary

- Backend tests: `199 passed`
- Frontend lint: passed
- Frontend build: passed
- Docker compose config: passed
- Docker full stack up/build: passed
- Endpoint smoke suite (`/health`, `/auth`, `/chat`, `/usage/summary`,
  `/reports/summary`, `/scenarios` create + summary): passed
- Deployment package (`render.yaml` + `docs/deployment.md`): present
- Known caveats: see notes below (non-blocking)

## Validation Details

### Backend tests

Recorded result:

```text
199 passed, 5 warnings
```

Backend test command:

```bash
cd backend
uv run pytest
```

### Frontend lint

Validated successfully:

```bash
cd frontend
pnpm lint
```

Result:

- Passed with no reported lint errors

### Frontend build

Validated successfully:

```bash
cd frontend
pnpm build
```

Observed result:

- compile completed successfully
- linting and type validation completed
- static pages were generated
- build traces completed

### Docker compose config

Validated successfully:

```bash
docker compose config
```

Result:

- Compose file resolved cleanly
- Service graph and healthchecks valid

### Docker full stack

Validated successfully:

```bash
docker compose up -d --build
docker compose ps
```

Observed status:

- `frontend`, `backend`, `postgres`, `redis`, `qdrant` all healthy
- image builds completed for backend/frontend
- service healthchecks green

### Endpoint smoke tests

Smoke flow included authenticated register/login and endpoint calls.

Endpoints validated:

- `GET /health` -> 200
- `POST /auth/register` -> 200
- `POST /auth/login` -> 200
- `POST /chat` -> 200
- `GET /usage/summary` -> 200
- `GET /reports/summary` -> 200
- `POST /scenarios` -> 200
- `GET /scenarios/summary` -> 200
- frontend root `GET /` -> 200 (`http://localhost:3000`)

### Deployment config status

Deployment packaging present and documented:

- `render.yaml` for split deployment baseline
- `docs/deployment.md` covering Vercel + Render/Railway + managed Postgres/Redis/Qdrant
- CI workflows validate backend/frontend/docker/security on PR/push
- Backend Docker image now includes `data/` so scenario and RAG runtime paths
  resolve consistently inside containers

## Known Local Environment Caveats

### Scenario packaging caveat resolved

Backend image packaging now copies the repository `data/` directory into
`/app/data`. Revalidated behavior:

- `POST /scenarios` -> 200 in Docker runtime
- `GET /scenarios/summary` -> 200 in Docker runtime

The previous missing-holdings-file caveat is resolved.

### Backend test warnings remain non-blocking

Observed warnings:

- deprecation warning for `HTTP_422_UNPROCESSABLE_ENTITY`
- pydantic serializer warning in plan serialization tests

Tests still pass and API behavior remains validated.

### Deterministic fallback mode is expected behavior

When optional provider keys are absent or providers are configured to `fallback`:

- chat remains usable
- investigation evidence remains deterministic
- demos stay stable offline

This is an intentional design choice for reviewer evaluation, not a degraded
error state.

## Notes for Reviewers

- AlphaLens is optimized for deterministic, reproducible product evaluation.
- Optional live providers are not required to assess the core workflow.
- Human approval, fallback behavior, and typed service boundaries are part of
  the evaluated system design.
