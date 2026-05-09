"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alphalens.api import deps
from alphalens.api.middleware import SecurityHeadersMiddleware
from alphalens.api.rate_limit import build_rate_limiter
from alphalens.api.routers import (
    agent,
    approvals,
    auth,
    conversations,
    feedback,
    health,
    investigations,
    knowledge,
    memory,
    plans,
    portfolio,
    rag,
    reports,
    runtime,
    scenarios,
    speech,
    usage,
)
from alphalens.core.config import Settings, get_settings
from alphalens.core.errors import register_exception_handlers
from alphalens.core.logging import configure_logging, get_logger
from alphalens.infrastructure.database import create_engine_from_settings
from alphalens.infrastructure.models import Base
from alphalens.infrastructure.schema_guards import ensure_dev_report_table_schema
from alphalens.infrastructure.observability.langsmith import setup_langsmith


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    log = get_logger("alphalens.api")
    log.info("api_startup", env=settings.app_env, version=settings.app_version)
    if settings.is_dev:
        speech_pm = "real" if settings.speech_enabled and bool(settings.openai_api_key) else "fallback"
        log.info(
            "speech_runtime_startup",
            openai_key_configured=bool(settings.openai_api_key),
            speech_provider_mode=speech_pm,
        )
    deps._persistence_runtime_state.cache_clear()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        try:
            engine = create_engine_from_settings(settings)
            Base.metadata.create_all(bind=engine)
            ensure_dev_report_table_schema(engine, app_env=settings.app_env)
            deps._persistence_runtime_state.cache_clear()
            deps._approval_repository.cache_clear()
            deps._approvals_service.cache_clear()
            deps._user_repository.cache_clear()
            deps._refresh_token_repository.cache_clear()
            deps._auth_service.cache_clear()
            deps._feedback_repository.cache_clear()
            deps._report_repository.cache_clear()
            deps._investigation_repository.cache_clear()
            deps._investigations_service.cache_clear()
            deps._scenario_repository.cache_clear()
            deps._usage_service.cache_clear()
            deps._memory_service.cache_clear()
        except Exception as exc:
            if settings.app_env not in {"dev", "test"}:
                raise
            log.warning(
                "persistence_startup_fallback",
                backend="in_memory",
                reason=f"{exc.__class__.__name__}: {exc}",
            )
    try:
        yield
    finally:
        log.info("api_shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    setup_langsmith(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=_lifespan,
        docs_url="/docs" if settings.docs_public_enabled else None,
        redoc_url="/redoc" if settings.docs_public_enabled else None,
        openapi_url="/openapi.json" if settings.docs_public_enabled else None,
    )
    app.state.settings = settings
    app.state.rate_limiter = build_rate_limiter(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(plans.router)
    app.include_router(portfolio.router)
    app.include_router(approvals.router)
    app.include_router(agent.router)
    app.include_router(agent.public_router)
    app.include_router(speech.router)
    app.include_router(memory.router)
    app.include_router(conversations.router)
    app.include_router(rag.router)
    app.include_router(knowledge.router)
    app.include_router(runtime.router)
    app.include_router(usage.router)
    app.include_router(feedback.router)
    app.include_router(reports.router)
    app.include_router(investigations.router)
    app.include_router(scenarios.router)

    return app


app = create_app()
