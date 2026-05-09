"""Runtime/provider status endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import SettingsDep, get_persistence_runtime_state
from alphalens.schemas.runtime import ProviderStatus, RuntimeStatusResponse
from alphalens.services.search_service import resolve_search_provider

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/status", response_model=RuntimeStatusResponse)
def runtime_status(
    settings: SettingsDep,
) -> RuntimeStatusResponse:
    persistence = get_persistence_runtime_state()
    effective_search_provider, search_external_enabled = resolve_search_provider(settings)
    providers = [
        ProviderStatus(
            name="OpenAI LLM",
            status="real" if settings.llm_enabled and bool(settings.openai_api_key) else "fallback",
            reason=None
            if settings.llm_enabled and settings.openai_api_key
            else "OPENAI_API_KEY not configured",
        ),
        ProviderStatus(
            name="Speech",
            status="real" if settings.speech_enabled and bool(settings.openai_api_key) else "fallback",
            reason=None
            if settings.speech_enabled and settings.openai_api_key
            else (
                "OPENAI_API_KEY not configured; microphone transcription unavailable"
                if settings.speech_enabled
                else "Speech disabled (SPEECH_ENABLED=false)"
            ),
        ),
        ProviderStatus(
            name="Market Data",
            status="real"
            if settings.market_data_provider == "alpha_vantage"
            and bool(settings.alpha_vantage_api_key)
            else "fallback",
            reason=None
            if settings.market_data_provider == "alpha_vantage" and settings.alpha_vantage_api_key
            else "ALPHA_VANTAGE_API_KEY not configured",
        ),
        ProviderStatus(
            name="Web/News",
            status="real" if search_external_enabled else "fallback",
            reason=None
            if search_external_enabled
            else "SERPER_API_KEY not configured",
        ),
        ProviderStatus(
            name="Macro",
            status="real" if settings.macro_data_provider == "fred" and bool(settings.fred_api_key) else "fallback",
            reason=None
            if settings.macro_data_provider == "fred" and settings.fred_api_key
            else "FRED_API_KEY not configured",
        ),
        ProviderStatus(
            name="SEC",
            status="real" if settings.sec_provider == "sec_edgar" else "fallback",
            reason=None if settings.sec_provider == "sec_edgar" else "SEC provider fallback is enabled",
        ),
        ProviderStatus(
            name="Qdrant",
            status="connected" if bool(settings.qdrant_url) else "fallback",
            reason=None if settings.qdrant_url else "QDRANT_URL not configured; in-memory retrieval fallback",
        ),
        ProviderStatus(
            name="Redis",
            status="connected" if bool(settings.redis_url) else "fallback",
            reason=None if settings.redis_url else "REDIS_URL not configured; in-memory cache fallback",
        ),
        ProviderStatus(
            name="Persistence",
            status=persistence.status,
            reason=persistence.reason,
        ),
        ProviderStatus(
            name="Plan quotas",
            status="real",
            reason=(
                "Dev quota bypass enabled"
                if settings.app_env == "dev" and settings.dev_bypass_quotas
                else None
            ),
        ),
    ]
    live_provider_present = any(
        provider.status in {"real", "connected"}
        for provider in providers
        if provider.name in {"OpenAI LLM", "Speech", "Market Data", "Web/News", "Macro", "SEC"}
    )
    return RuntimeStatusResponse(
        workspace_mode="live" if live_provider_present else "demo",
        providers=providers,
        data_sources={
            "portfolio": "synthetic",
            "knowledge_base": "seeded_internal_docs",
            "users": persistence.users,
            "refresh_tokens": persistence.refresh_tokens,
            "approvals": persistence.approvals,
            "reports": persistence.reports,
            "investigations": persistence.investigations,
            "feedback": persistence.feedback,
            "usage": persistence.usage,
            "external_market": "fallback" if providers[2].status == "fallback" else "alpha_vantage",
            "external_web_news": effective_search_provider,
        },
    )
