# Deployment

AlphaLens supports a split deployment model suitable for portfolio review demos and production-style architecture reviews.

## 1) Deployment Options

### Frontend

- Vercel

### Backend

- Render
- Railway
- Fly.io
- Azure App Service
- AWS ECS

### Data Services

- managed Postgres
- Upstash Redis or managed Redis
- Qdrant Cloud

## 2) Recommended Topology

- deploy frontend and backend as separate services;
- expose backend over HTTPS;
- use frontend proxy route (`/api/backend`) with `BACKEND_INTERNAL_URL` pointing to backend origin;
- keep CORS strict to known frontend origins.

## 3) Secrets and Environment Variables

Never commit secrets. Store only in platform secret managers.

Minimum secrets checklist:
- OpenAI key
- Serper key
- FRED key
- Alpha Vantage key
- JWT secrets
- database URLs
- Redis URLs
- Qdrant URLs

Common production runtime variables:
- `APP_ENV=prod`
- `APP_DATABASE_URL`
- `DATABASE_URL` (if required by platform/tooling)
- `REDIS_URL`
- `RATE_LIMIT_REDIS_URL`
- `QDRANT_URL`
- `QDRANT_API_KEY` (if needed)
- `CORS_ALLOW_ORIGINS`
- `NEXT_PUBLIC_API_URL=/api/backend`
- `BACKEND_INTERNAL_URL=https://<backend-domain>`

## 4) Platform Notes

- `render.yaml` can be used as a baseline for Render.
- Equivalent build/start commands work for Railway and similar PaaS.
- For container platforms (Fly.io, Azure App Service with containers, AWS ECS), reuse existing backend/frontend Dockerfiles.

## 5) Deployment Smoke Checklist

Run this checklist after each deployment:

1. health endpoint (`/health`)
2. runtime status page/API
3. auth (register/login/refresh)
4. chat endpoint and UI chat flow
5. RAG upload/retrieval flow
6. speech endpoint behavior (enabled/disabled path)
7. reports workflow
8. scenarios workflow
9. usage metrics page/API

## 6) Production Safety Notes

- Do not expose `docker compose config` output in logs/docs if it could resolve secrets.
- Do not commit `.env`.
- Use managed migrations such as Alembic for production schema changes.

## 7) Fallback and Demo Reliability

Fallback providers are intentionally supported so deployment demos remain stable when real provider keys are absent. This allows deterministic reviewer flows without blocking on external API availability.
