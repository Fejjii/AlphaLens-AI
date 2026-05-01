"""Usage repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.infrastructure.models import UsageEventModel
from alphalens.schemas.usage import UsageEvent, UsageSummary


class UsageRepository(Protocol):
    def create(self, event: UsageEvent) -> UsageEvent: ...
    def list(self, *, user_id: str | None = None) -> list[UsageEvent]: ...


@dataclass(slots=True)
class InMemoryUsageRepository(UsageRepository):
    _events: list[UsageEvent] = field(default_factory=list)
    def create(self, event: UsageEvent) -> UsageEvent:
        self._events.append(event)
        return event
    def list(self, *, user_id: str | None = None) -> list[UsageEvent]:
        if user_id is None:
            return list(self._events)
        return [event for event in self._events if event.user_id == user_id]
    def clear(self) -> None:
        self._events.clear()


class SqlAlchemyUsageRepository(UsageRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
    def create(self, event: UsageEvent) -> UsageEvent:
        with self._session_factory() as session:
            session.add(_to_model(event))
            session.commit()
        return event
    def list(self, *, user_id: str | None = None) -> list[UsageEvent]:
        with self._session_factory() as session:
            query = session.query(UsageEventModel)
            if user_id is not None:
                query = query.filter(UsageEventModel.user_id == user_id)
            rows = query.order_by(UsageEventModel.created_at.desc()).all()
            return [_to_schema(row) for row in rows]


def _to_model(event: UsageEvent) -> UsageEventModel:
    return UsageEventModel(
        usage_id=event.usage_id,
        user_id=event.user_id,
        conversation_id=event.conversation_id,
        created_at=event.created_at,
        event_type=event.event_type,
        provider=event.provider,
        model=event.model,
        input_tokens=event.input_tokens,
        output_tokens=event.output_tokens,
        total_tokens=event.total_tokens,
        estimated_cost_usd=event.estimated_cost_usd,
        tool_name=event.tool_name,
        metadata_json=event.metadata,
    )


def _to_schema(model: UsageEventModel) -> UsageEvent:
    return UsageEvent(
        usage_id=model.usage_id,
        created_at=model.created_at,
        user_id=model.user_id,
        conversation_id=model.conversation_id,
        event_type=model.event_type,  # type: ignore[arg-type]
        provider=model.provider,
        model=model.model,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        total_tokens=model.total_tokens,
        estimated_cost_usd=model.estimated_cost_usd,
        tool_name=model.tool_name,
        metadata=model.metadata_json,
    )
