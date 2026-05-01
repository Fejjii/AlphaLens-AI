"""FastAPI dependency providers.

Services are simple and stateless today, so we instantiate per-request
to keep wiring obvious. When they grow lifecycle (e.g. clients, pools),
swap to module-level singletons or `lifespan`-managed instances.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from alphalens.core.config import Settings, get_settings
from alphalens.infrastructure.cache import build_cache_backend
from alphalens.infrastructure.database import get_session_factory
from alphalens.memory.sqlalchemy_memory import SqlAlchemyMemoryStore
from alphalens.memory.service import MemoryService, get_memory_service
from alphalens.repositories.approvals import (
    ApprovalRepository,
    InMemoryApprovalRepository,
    SqlAlchemyApprovalRepository,
)
from alphalens.repositories.feedback import (
    FeedbackRepository,
    InMemoryFeedbackRepository,
    SqlAlchemyFeedbackRepository,
)
from alphalens.repositories.reports import (
    InMemoryReportRepository,
    ReportRepository,
    SqlAlchemyReportRepository,
)
from alphalens.repositories.scenarios import (
    InMemoryScenarioRepository,
    ScenarioRepository,
    SqlAlchemyScenarioRepository,
)
from alphalens.repositories.usage import InMemoryUsageRepository, SqlAlchemyUsageRepository
from alphalens.repositories.users import (
    InMemoryUserRepository,
    SqlAlchemyUserRepository,
    UserRepository,
)
from alphalens.services.auth_service import (
    AuthError,
    AuthService,
    InactiveUserError,
)
from alphalens.services.approvals_service import ApprovalsService
from alphalens.services.feedback_service import FeedbackService
from alphalens.services.cache_service import CacheService
from alphalens.services.chat_service import ChatService
from alphalens.services.llm_service import LLMService, get_llm_service
from alphalens.services.macro_service import MacroService, get_macro_service
from alphalens.services.market_data_service import (
    MarketDataService,
    get_market_data_service,
)
from alphalens.services.portfolio_service import PortfolioService
from alphalens.services.rag_service import RAGService
from alphalens.services.search_service import SearchService, get_search_service
from alphalens.services.sec_service import SECService, get_sec_service
from alphalens.services.speech_service import SpeechService, get_speech_service as build_speech_service
from alphalens.services.reports_service import ReportsService
from alphalens.services.scenarios_service import ScenariosService
from alphalens.services.plan_service import PlanService
from alphalens.services.usage_service import UsageService
from alphalens.api.middleware import SimpleRateLimiter
from alphalens.schemas.user import UserProfile

SettingsDep = Annotated[Settings, Depends(get_settings)]
_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _portfolio_service() -> PortfolioService:
    return PortfolioService()


@lru_cache(maxsize=1)
def _approval_repository() -> ApprovalRepository:
    settings = get_settings()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        session_factory = get_session_factory(settings)
        return SqlAlchemyApprovalRepository(session_factory)
    return InMemoryApprovalRepository()


@lru_cache(maxsize=1)
def _user_repository() -> UserRepository:
    settings = get_settings()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        try:
            session_factory = get_session_factory(settings)
            return SqlAlchemyUserRepository(session_factory)
        except Exception:
            if settings.app_env in {"dev", "test"}:
                return InMemoryUserRepository()
            raise
    return InMemoryUserRepository()


@lru_cache(maxsize=1)
def _auth_service() -> AuthService:
    return AuthService(settings=get_settings(), repository=_user_repository())


@lru_cache(maxsize=1)
def _approvals_service() -> ApprovalsService:
    return ApprovalsService(repository=_approval_repository())


@lru_cache(maxsize=1)
def _cache_service() -> CacheService:
    settings = get_settings()
    backend = build_cache_backend(settings)
    return CacheService(
        backend=backend,
        default_ttl_seconds=settings.cache_ttl_seconds,
        enabled=settings.cache_enabled,
        usage_service=_usage_service(),
    )


@lru_cache(maxsize=1)
def _rag_service() -> RAGService:
    return RAGService(get_settings(), cache=_cache_service())


@lru_cache(maxsize=1)
def _llm_service() -> LLMService:
    return get_llm_service(get_settings(), usage_service=_usage_service())


@lru_cache(maxsize=1)
def _market_data_service() -> MarketDataService:
    return get_market_data_service(get_settings(), cache=_cache_service())


@lru_cache(maxsize=1)
def _search_service() -> SearchService:
    return get_search_service(get_settings(), cache=_cache_service())


@lru_cache(maxsize=1)
def _macro_service() -> MacroService:
    return get_macro_service(get_settings(), cache=_cache_service())


@lru_cache(maxsize=1)
def _sec_service() -> SECService:
    return get_sec_service(get_settings(), cache=_cache_service())


@lru_cache(maxsize=1)
def _usage_service() -> UsageService:
    settings = get_settings()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        return UsageService(repository=SqlAlchemyUsageRepository(get_session_factory(settings)))
    return UsageService(repository=InMemoryUsageRepository())


@lru_cache(maxsize=1)
def _plan_service() -> PlanService:
    return PlanService(settings=get_settings(), usage_service=_usage_service())


@lru_cache(maxsize=1)
def _feedback_repository() -> FeedbackRepository:
    settings = get_settings()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        return SqlAlchemyFeedbackRepository(get_session_factory(settings))
    return InMemoryFeedbackRepository()


@lru_cache(maxsize=1)
def _feedback_service() -> FeedbackService:
    return FeedbackService(repository=_feedback_repository(), usage_service=_usage_service())


@lru_cache(maxsize=1)
def _report_repository() -> ReportRepository:
    settings = get_settings()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        return SqlAlchemyReportRepository(get_session_factory(settings))
    return InMemoryReportRepository()


@lru_cache(maxsize=1)
def _reports_service() -> ReportsService:
    return ReportsService(
        repository=_report_repository(),
        usage_service=_usage_service(),
        memory_service=_memory_service(),
    )


@lru_cache(maxsize=1)
def _scenario_repository() -> ScenarioRepository:
    settings = get_settings()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        return SqlAlchemyScenarioRepository(get_session_factory(settings))
    return InMemoryScenarioRepository()


@lru_cache(maxsize=1)
def _scenarios_service() -> ScenariosService:
    return ScenariosService(
        repository=_scenario_repository(),
        usage_service=_usage_service(),
    )


@lru_cache(maxsize=1)
def _memory_service() -> MemoryService:
    settings = get_settings()
    if settings.persistence_backend == "postgres" and settings.app_database_url:
        return MemoryService(
            store=SqlAlchemyMemoryStore(get_session_factory(settings)),
            enabled=settings.memory_enabled,
        )
    return get_memory_service(settings)


@lru_cache(maxsize=1)
def _speech_service() -> SpeechService:
    return build_speech_service(get_settings())


@lru_cache(maxsize=1)
def _rate_limiter() -> SimpleRateLimiter:
    return SimpleRateLimiter()


@lru_cache(maxsize=1)
def _chat_service() -> ChatService:
    return ChatService(
        settings=get_settings(),
        rag_service=_rag_service(),
        approvals_service=_approvals_service(),
        llm_service=_llm_service(),
        market_data_service=_market_data_service(),
        search_service=_search_service(),
        macro_service=_macro_service(),
        sec_service=_sec_service(),
        usage_service=_usage_service(),
        memory_service=_memory_service(),
    )


def get_portfolio_service() -> PortfolioService:
    return _portfolio_service()


def get_approvals_service() -> ApprovalsService:
    return _approvals_service()


def get_chat_service() -> ChatService:
    return _chat_service()


def get_rag_service() -> RAGService:
    return _rag_service()


def get_usage_service() -> UsageService:
    return _usage_service()


def get_memory_service_dep() -> MemoryService:
    return _memory_service()


def get_speech_service() -> SpeechService:
    return _speech_service()


def get_feedback_service() -> FeedbackService:
    return _feedback_service()


def get_reports_service() -> ReportsService:
    return _reports_service()


def get_scenarios_service() -> ScenariosService:
    return _scenarios_service()


def get_rate_limiter() -> SimpleRateLimiter:
    return _rate_limiter()


def get_plan_service() -> PlanService:
    return _plan_service()


def get_auth_service() -> AuthService:
    return _auth_service()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UserProfile:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )
    auth_service = get_auth_service()
    try:
        return auth_service.resolve_current_user(credentials.credentials)
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


PortfolioServiceDep = Annotated[PortfolioService, Depends(get_portfolio_service)]
ApprovalsServiceDep = Annotated[ApprovalsService, Depends(get_approvals_service)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]
UsageServiceDep = Annotated[UsageService, Depends(get_usage_service)]
MemoryServiceDep = Annotated[MemoryService, Depends(get_memory_service_dep)]
SpeechServiceDep = Annotated[SpeechService, Depends(get_speech_service)]
FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]
ReportsServiceDep = Annotated[ReportsService, Depends(get_reports_service)]
ScenariosServiceDep = Annotated[ScenariosService, Depends(get_scenarios_service)]
PlanServiceDep = Annotated[PlanService, Depends(get_plan_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
CurrentUserDep = Annotated[UserProfile, Depends(get_current_user)]
