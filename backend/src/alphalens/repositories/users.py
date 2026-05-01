"""User repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import UserModel
from alphalens.schemas.user import UserPlan, UserProfile, UserResponse, UserRole


class UserRepository(Protocol):
    def create(self, user: UserResponse, *, password_hash: str) -> UserProfile: ...

    def get_by_email(self, email: str) -> UserProfile | None: ...

    def get_by_id(self, user_id: str) -> UserProfile | None: ...

    def get_password_hash(self, user_id: str) -> str | None: ...

    def update(self, user: UserResponse, *, password_hash: str | None = None) -> UserProfile: ...


@dataclass(slots=True)
class _StoredUser:
    profile: UserProfile
    password_hash: str


@dataclass(slots=True)
class InMemoryUserRepository(UserRepository):
    _records: dict[str, _StoredUser] = field(default_factory=dict)
    _email_index: dict[str, str] = field(default_factory=dict)

    def create(self, user: UserResponse, *, password_hash: str) -> UserProfile:
        profile = UserProfile.model_validate(user.model_dump(mode="json"))
        self._records[profile.id] = _StoredUser(profile=profile, password_hash=password_hash)
        self._email_index[profile.email.lower()] = profile.id
        return profile

    def get_by_email(self, email: str) -> UserProfile | None:
        user_id = self._email_index.get(email.lower())
        if user_id is None:
            return None
        stored = self._records.get(user_id)
        return stored.profile if stored is not None else None

    def get_by_id(self, user_id: str) -> UserProfile | None:
        stored = self._records.get(user_id)
        return stored.profile if stored is not None else None

    def get_password_hash(self, user_id: str) -> str | None:
        stored = self._records.get(user_id)
        return stored.password_hash if stored is not None else None

    def update(self, user: UserResponse, *, password_hash: str | None = None) -> UserProfile:
        existing = self._records[user.id]
        profile = UserProfile.model_validate(user.model_dump(mode="json"))
        self._records[user.id] = _StoredUser(
            profile=profile,
            password_hash=password_hash or existing.password_hash,
        )
        self._email_index[profile.email.lower()] = profile.id
        return profile

    def clear(self) -> None:
        self._records.clear()
        self._email_index.clear()


class SqlAlchemyUserRepository(UserRepository):
    """SQLAlchemy-backed repository for user accounts."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, user: UserResponse, *, password_hash: str) -> UserProfile:
        with self._session_factory() as session:
            model = _to_model(user, password_hash=password_hash)
            session.add(model)
            session.commit()
            return _to_schema(model)

    def get_by_email(self, email: str) -> UserProfile | None:
        with self._session_factory() as session:
            row = session.query(UserModel).filter(UserModel.email == email.lower()).one_or_none()
            return _to_schema(row) if row is not None else None

    def get_by_id(self, user_id: str) -> UserProfile | None:
        with self._session_factory() as session:
            row = session.get(UserModel, user_id)
            return _to_schema(row) if row is not None else None

    def get_password_hash(self, user_id: str) -> str | None:
        with self._session_factory() as session:
            row = session.get(UserModel, user_id)
            return row.password_hash if row is not None else None

    def update(self, user: UserResponse, *, password_hash: str | None = None) -> UserProfile:
        with self._session_factory() as session:
            row = session.get(UserModel, user.id)
            if row is None:
                row = _to_model(user, password_hash=password_hash or "")
                session.add(row)
            else:
                row.email = user.email.lower()
                row.full_name = user.full_name
                row.role = user.role.value
                row.plan = user.plan.value
                row.is_active = user.is_active
                row.created_at = user.created_at
                row.updated_at = user.updated_at
                if password_hash is not None:
                    row.password_hash = password_hash
            session.commit()
            return _to_schema(row)


def _to_model(user: UserResponse, *, password_hash: str) -> UserModel:
    return UserModel(
        id=user.id,
        email=user.email.lower(),
        password_hash=password_hash,
        full_name=user.full_name,
        role=user.role.value,
        plan=user.plan.value,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _to_schema(model: UserModel) -> UserProfile:
    return UserProfile(
        id=model.id,
        email=model.email,
        full_name=model.full_name,
        role=UserRole(model.role),
        plan=UserPlan(model.plan),
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
