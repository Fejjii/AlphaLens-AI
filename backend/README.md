# AlphaLens backend

FastAPI service exposing the agentic investment intelligence API.

## Stack

- Python 3.11, [uv](https://docs.astral.sh/uv/) for env + dependency management
- FastAPI + Pydantic v2 + `pydantic-settings`
- LangGraph (agent orchestration skeleton, mocked)
- structlog for structured logging
- pytest + httpx for tests
- Ruff for lint/format

## Install

```bash
uv sync --extra dev
```

## Run

```bash
uv run uvicorn alphalens.api.main:app --reload
```

OpenAPI docs at http://localhost:8000/docs.

## Test

```bash
uv run pytest
```

## Lint

```bash
uv run ruff check .
uv run ruff format .
```

## Layout

```
src/alphalens/
  api/             FastAPI app + routers + DI
  core/            config, logging, errors
  schemas/         Pydantic v2 request/response models
  agents/          LangGraph state + graph + nodes
  services/        Use-case orchestration (mock data today)
  tools/           Agent tool registry (Protocol)
  rag/             Retriever interfaces and stubs
  integrations/    External market/broker adapters (Protocol)
  infrastructure/  DB, cache, vectorstore clients (lazy stubs)
  evaluation/      Eval harness placeholder
```
