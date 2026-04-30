"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alphalens.api import deps
from alphalens.api.routers import agent, approvals, feedback, health, memory, portfolio, rag, reports, scenarios, speech, usage
from alphalens.core.config import Settings, get_settings
from alphalens.core.errors import register_exception_handlers
from alphalens.core.logging import configure_logging, get_logger
from alphalens.infrastructure.database import create_engine_from_settings
from alphalens.infrastructure.models import Base
from alphalens.infrastructure.observability.langsmith import setup_langsmith


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    log = get_logger("alphalens.api")
    log.info("api_startup", env=settings.app_env, version=settings.app_version)
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        engine = create_engine_from_settings(settings)
        Base.metadata.create_all(bind=engine)
        deps._approval_repository.cache_clear()
        deps._approvals_service.cache_clear()
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
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(portfolio.router)
    app.include_router(approvals.router)
    app.include_router(agent.router)
    app.include_router(agent.public_router)
    app.include_router(speech.router)
    app.include_router(memory.router)
    app.include_router(rag.router)
    app.include_router(usage.router)
    app.include_router(feedback.router)
    app.include_router(reports.router)
    app.include_router(scenarios.router)

    return app


app = create_app()
