from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
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
            record.revoked_at = datetime.utcnow()


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
    def create(self, record: RefreshTokenRecord) -> RefreshTokenRecord:
        with self._session_factory() as session:
            session.add(RefreshTokenModel(**record.__dict__))
            session.commit()
        return record
    def get_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        with self._session_factory() as session:
            row = session.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == token_hash).one_or_none()
            if row is None:
                return None
            return RefreshTokenRecord(row.id, row.user_id, row.token_hash, row.expires_at, row.revoked_at, row.created_at)
    def revoke(self, token_hash: str) -> None:
        with self._session_factory() as session:
            row = session.query(RefreshTokenModel).filter(RefreshTokenModel.token_hash == token_hash).one_or_none()
            if row is not None:
                row.revoked_at = datetime.utcnow()
                session.commit()


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
