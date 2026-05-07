from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alphalens.core.config import Settings
from alphalens.infrastructure.database import Base
from alphalens.repositories.auth_sessions import (
    SqlAlchemyRefreshTokenRepository,
    hash_refresh_token,
)
from alphalens.repositories.users import SqlAlchemyUserRepository
from alphalens.schemas.user import UserCreate, UserLogin
from alphalens.services.auth_service import AuthService


def _build_settings(database_url: str) -> Settings:
    return Settings(
        APP_ENV="test",
        PERSISTENCE_BACKEND="postgres",
        APP_DATABASE_URL=database_url,
        AUTH_SECRET_KEY="test-secret-key",
    )


def _build_session_factory(db_path: Path) -> sessionmaker:
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _build_auth_service(settings: Settings, factory: sessionmaker) -> AuthService:
    return AuthService(
        settings=settings,
        repository=SqlAlchemyUserRepository(factory),
        refresh_repository=SqlAlchemyRefreshTokenRepository(factory),
    )


def test_auth_persists_users_and_refresh_tokens_across_service_recreation(tmp_path: Path) -> None:
    db_path = tmp_path / "auth_persistence.sqlite3"
    database_url = f"sqlite+pysqlite:///{db_path}"
    settings = _build_settings(database_url)
    session_factory = _build_session_factory(db_path)

    first_service = _build_auth_service(settings, session_factory)
    token = first_service.register_user(
        UserCreate(
            email="durable@example.com",
            password="Password123!",
            full_name="Durable User",
        )
    )

    durable_user_repo = SqlAlchemyUserRepository(session_factory)
    stored_user = durable_user_repo.get_by_email("durable@example.com")
    assert stored_user is not None
    assert stored_user.email == "durable@example.com"

    second_service = _build_auth_service(settings, session_factory)
    login = second_service.login_user(
        UserLogin(email="durable@example.com", password="Password123!")
    )
    assert login.user.email == "durable@example.com"

    refresh_repo = SqlAlchemyRefreshTokenRepository(session_factory)
    persisted_refresh = refresh_repo.get_by_hash(hash_refresh_token(token.refresh_token))
    assert persisted_refresh is not None
    assert persisted_refresh.user_id == stored_user.id

    second_service.logout(token.refresh_token)
    revoked_refresh = SqlAlchemyRefreshTokenRepository(session_factory).get_by_hash(
        hash_refresh_token(token.refresh_token)
    )
    assert revoked_refresh is not None
    assert revoked_refresh.revoked_at is not None
