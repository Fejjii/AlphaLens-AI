"""Authentication and user account schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import EmailStr, Field

from alphalens.schemas.common import APIModel


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    REVIEWER = "reviewer"


class UserPlan(str, Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


class UserCreate(APIModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=200)


class UserLogin(APIModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(APIModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    plan: UserPlan
    is_active: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class UserProfile(UserResponse):
    """Current authenticated user view."""


class TokenResponse(APIModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


class TokenClaims(APIModel):
    sub: str
    email: EmailStr
    role: UserRole
    plan: UserPlan
    is_active: bool
    exp: int
