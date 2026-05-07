from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import RefreshTokenModel


@dataclass(slots=True)
class RefreshTokenRecord:
    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class RefreshTokenRepository(Protocol):
    def create(self, record: RefreshTokenRecord) -> RefreshTokenRecord: ...
    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None: ...
    def revoke(self, token_hash: str) -> None: ...


@dataclass(slots=True)
class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    _records: dict[str, RefreshTokenRecord] = field(default_factory=dict)
    def create(self, record: RefreshTokenRecord) -> RefreshTokenRecord:
        self._records[record.token_hash] = record
        return record
    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        return self._records.get(token_hash)
    def revoke(self, token_hash: str) -> None:
        record = self._records.get(token_hash)
        if record:
            record.revoked_at = datetime.now(tz=UTC)


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
    def create(self, record: RefreshTokenRecord) -> RefreshTokenRecord:
        with self._session_factory() as session:
            session.add(
                RefreshTokenModel(
                    id=record.id,
                    user_id=record.user_id,
                    token_hash=record.token_hash,
                    expires_at=record.expires_at,
                    revoked_at=record.revoked_at,
                    created_at=record.created_at,
                )
            )
            session.commit()
        return record
    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        with self._session_factory() as session:
            row = session.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == token_hash).one_or_none()
            if row is None:
                return None
            return RefreshTokenRecord(
                row.id,
                row.user_id,
                row.token_hash,
                _as_utc(row.expires_at),
                _as_utc(row.revoked_at),
                _as_utc(row.created_at),
            )
    def revoke(self, token_hash: str) -> None:
        with self._session_factory() as session:
            row = session.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == token_hash).one_or_none()
            if row is not None:
                row.revoked_at = datetime.now(tz=UTC)
                session.commit()


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
