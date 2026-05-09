"""Authentication service for user registration, login, and token resolution."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Callable

import jwt
from passlib.context import CryptContext

from alphalens.core.config import Settings
from alphalens.repositories.auth_sessions import (
    InMemoryRefreshTokenRepository,
    RefreshTokenRecord,
    RefreshTokenRepository,
    hash_refresh_token,
)
from alphalens.repositories.users import InMemoryUserRepository, UserRepository
from alphalens.schemas.user import (
    TokenClaims,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserPlan,
    UserProfile,
    UserResponse,
    UserRole,
)

_INVALID_CREDENTIALS = "Invalid email or password."


class AuthError(Exception):
    """Raised when authentication fails."""


class TokenExpiredError(AuthError):
    """Raised when the access token is past its expiry."""


class InactiveUserError(AuthError):
    """Raised when an inactive user tries to authenticate."""


class DuplicateUserError(AuthError):
    """Raised when a user already exists."""


class AuthService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: UserRepository | None = None,
        refresh_repository: RefreshTokenRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or InMemoryUserRepository()
        self._refresh_repository = refresh_repository or InMemoryRefreshTokenRepository()
        self._now_provider = now_provider or (lambda: datetime.now(tz=UTC))
        self._id_factory = id_factory or (lambda: f"usr_{uuid.uuid4().hex[:12]}")
        self._password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

    def register_user(self, payload: UserCreate) -> TokenResponse:
        if self._repository.get_by_email(payload.email) is not None:
            raise DuplicateUserError("A user with this email already exists.")
        now = self._now_provider()
        user = UserResponse(
            id=self._id_factory(),
            email=payload.email,
            full_name=payload.full_name,
            role=UserRole.USER,
            plan=UserPlan.FREE,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        profile = self._repository.create(
            user,
            password_hash=self.hash_password(payload.password),
        )
        return self.create_token_response(profile)

    def login_user(self, payload: UserLogin) -> TokenResponse:
        profile = self._repository.get_by_email(payload.email)
        if profile is None:
            raise AuthError(_INVALID_CREDENTIALS)
        password_hash = self._repository.get_password_hash(profile.id)
        if password_hash is None or not self.verify_password(payload.password, password_hash):
            raise AuthError(_INVALID_CREDENTIALS)
        if not profile.is_active:
            raise InactiveUserError("This user account is inactive.")
        return self.create_token_response(profile)

    def hash_password(self, password: str) -> str:
        return self._password_context.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        return self._password_context.verify(password, password_hash)

    def create_access_token(self, user: UserProfile, *, expires_at: datetime | None = None) -> str:
        expiry = expires_at or (
            self._now_provider()
            + timedelta(minutes=self._settings.auth_access_token_expire_minutes)
        )
        claims = TokenClaims(
            sub=user.id,
            email=user.email,
            role=user.role,
            plan=user.plan,
            is_active=user.is_active,
            exp=int(expiry.timestamp()),
        )
        return jwt.encode(
            claims.model_dump(mode="json"),
            self._settings.auth_secret_key,
            algorithm=self._settings.auth_algorithm,
        )

    def decode_access_token(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._settings.auth_secret_key,
                algorithms=[self._settings.auth_algorithm],
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError("Access token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthError("Invalid access token.") from exc
        claims = TokenClaims.model_validate(payload)
        if not claims.is_active:
            raise InactiveUserError("This user account is inactive.")
        return claims

    def resolve_current_user(self, token: str) -> UserProfile:
        claims = self.decode_access_token(token)
        user = self._repository.get_by_id(claims.sub)
        if user is None:
            raise AuthError("Authenticated user no longer exists.")
        if not user.is_active:
            raise InactiveUserError("This user account is inactive.")
        return user

    def create_token_response(self, user: UserProfile) -> TokenResponse:
        token = self.create_access_token(user)
        refresh_token = self.create_refresh_token(user)
        return TokenResponse(
            access_token=token,
            refresh_token=refresh_token,
            expires_in=self._settings.auth_access_token_expire_minutes * 60,
            user=user,
        )

    def create_refresh_token(self, user: UserProfile) -> str:
        raw = f"rft_{uuid.uuid4().hex}_{user.id}"
        now = self._now_provider()
        expires_at = now + timedelta(days=self._settings.auth_refresh_token_expire_days)
        self._refresh_repository.create(
            RefreshTokenRecord(
                id=f"rftrec_{uuid.uuid4().hex[:12]}",
                user_id=user.id,
                token_hash=hash_refresh_token(raw),
                expires_at=expires_at,
                revoked_at=None,
                created_at=now,
            )
        )
        return raw

    def refresh_session(self, refresh_token: str) -> TokenResponse:
        record = self._refresh_repository.get_by_hash(hash_refresh_token(refresh_token))
        if record is None or record.revoked_at is not None or record.expires_at <= self._now_provider():
            raise AuthError("Invalid or expired refresh token.")
        user = self._repository.get_by_id(record.user_id)
        if user is None:
            raise AuthError("Authenticated user no longer exists.")
        if not user.is_active:
            raise InactiveUserError("This user account is inactive.")
        self._refresh_repository.revoke(record.token_hash)
        return self.create_token_response(user)

    def logout(self, refresh_token: str) -> None:
        self._refresh_repository.revoke(hash_refresh_token(refresh_token))

    def build_test_access_token(
        self,
        user: UserProfile,
        *,
        expires_at: datetime | None = None,
    ) -> str:
        return self.create_access_token(user, expires_at=expires_at)
