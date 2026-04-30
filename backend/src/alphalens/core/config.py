"""Application settings, loaded from environment variables and .env files."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["dev", "staging", "prod", "test"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
MarketDataProvider = Literal["fallback", "alpha_vantage"]
SearchProvider = Literal["fallback", "serper"]
MacroDataProvider = Literal["fallback", "fred"]
SECProvider = Literal["fallback", "sec_edgar"]
MemoryBackend = Literal["in_memory", "redis"]
PersistenceBackend = Literal["in_memory", "postgres"]


class Settings(BaseSettings):
    """Runtime configuration.

    Values are sourced from (in priority order): explicit kwargs, environment
    variables, then a local `.env` file. Unknown variables are ignored so the
    same `.env` can be shared with the frontend and infra layers.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AlphaLens AI"
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_env: Environment = Field(default="dev", alias="APP_ENV")
    log_level: LogLevel = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    app_database_url: str | None = Field(default=None, alias="APP_DATABASE_URL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")

    knowledge_base_path: str = Field(
        default="data/knowledge_base",
        alias="KNOWLEDGE_BASE_PATH",
        description="Filesystem path to markdown documents ingested into the RAG store.",
    )
    rag_collection: str = Field(default="alphalens_kb", alias="RAG_COLLECTION")
    rag_embedding_dim: int = Field(default=128, alias="RAG_EMBEDDING_DIM")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_temperature: float = Field(default=0.2, ge=0.0, le=2.0, alias="OPENAI_TEMPERATURE")
    openai_top_p: float = Field(default=1.0, ge=0.0, le=1.0, alias="OPENAI_TOP_P")
    llm_enabled: bool = Field(default=True, alias="LLM_ENABLED")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    speech_enabled: bool = Field(default=True, alias="SPEECH_ENABLED")
    default_response_language: str = Field(
        default="auto", alias="DEFAULT_RESPONSE_LANGUAGE"
    )
    speech_max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        gt=0,
        alias="SPEECH_MAX_UPLOAD_BYTES",
    )

    alpha_vantage_api_key: str | None = Field(
        default=None, alias="ALPHA_VANTAGE_API_KEY"
    )
    market_data_provider: MarketDataProvider = Field(
        default="fallback", alias="MARKET_DATA_PROVIDER"
    )
    market_data_timeout_seconds: float = Field(
        default=10.0, gt=0, le=60, alias="MARKET_DATA_TIMEOUT_SECONDS"
    )

    serper_api_key: str | None = Field(default=None, alias="SERPER_API_KEY")
    search_provider: SearchProvider = Field(
        default="fallback", alias="SEARCH_PROVIDER"
    )
    search_timeout_seconds: float = Field(
        default=10.0, gt=0, le=60, alias="SEARCH_TIMEOUT_SECONDS"
    )

    fred_api_key: str | None = Field(default=None, alias="FRED_API_KEY")
    macro_data_provider: MacroDataProvider = Field(
        default="fallback", alias="MACRO_DATA_PROVIDER"
    )
    macro_data_timeout_seconds: float = Field(
        default=10.0, gt=0, le=60, alias="MACRO_DATA_TIMEOUT_SECONDS"
    )

    sec_provider: SECProvider = Field(default="fallback", alias="SEC_PROVIDER")
    sec_timeout_seconds: float = Field(
        default=10.0, gt=0, le=60, alias="SEC_TIMEOUT_SECONDS"
    )
    sec_user_agent: str = Field(
        default="AlphaLens AI contact@example.com",
        alias="SEC_USER_AGENT",
    )

    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # Caching (Redis-backed when configured, in-memory otherwise).
    # `redis_url` is shared with the existing infrastructure setting above.
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_ttl_seconds: int = Field(default=300, gt=0, alias="CACHE_TTL_SECONDS")

    # Conversation memory.
    memory_enabled: bool = Field(default=True, alias="MEMORY_ENABLED")
    memory_backend: MemoryBackend = Field(default="in_memory", alias="MEMORY_BACKEND")
    memory_ttl_seconds: int = Field(default=3600, gt=0, alias="MEMORY_TTL_SECONDS")

    # Durable persistence backend for mutable workflow entities.
    persistence_backend: PersistenceBackend = Field(
        default="in_memory",
        alias="PERSISTENCE_BACKEND",
    )

    # LangSmith observability (all optional; tracing is a no-op when disabled)
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str | None = Field(default=None, alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="AlphaLens AI", alias="LANGCHAIN_PROJECT")

    @property
    def langsmith_enabled(self) -> bool:
        """True only when tracing flag is set and an API key is available."""
        return self.langchain_tracing_v2 and bool(self.langchain_api_key)

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached `Settings` instance.

    Cached so that environment is read once per process. Tests can clear the
    cache via `get_settings.cache_clear()` if they need to override env vars.
    """

    return Settings()
