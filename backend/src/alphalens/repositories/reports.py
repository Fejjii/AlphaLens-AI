"""Report repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from alphalens.core.json_safe import to_json_safe
from alphalens.infrastructure.models import ReportModel
from alphalens.schemas.agent import EvidenceItem
from alphalens.schemas.report import (
    ReportGenerationMeta,
    ReportResponse,
    ReportSection,
    ReportStatus,
    ReportType,
)


class ReportRepository(Protocol):
    def create(self, report: ReportResponse) -> ReportResponse: ...

    def list(self, *, user_id: str) -> list[ReportResponse]: ...

    def get(self, report_id: str, *, user_id: str) -> ReportResponse | None: ...


@dataclass(slots=True)
class InMemoryReportRepository(ReportRepository):
    _records: dict[str, ReportResponse] = field(default_factory=dict)

    def create(self, report: ReportResponse) -> ReportResponse:
        self._records[report.id] = report
        return report

    def list(self, *, user_id: str) -> list[ReportResponse]:
        records = [item for item in self._records.values() if item.user_id == user_id]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get(self, report_id: str, *, user_id: str) -> ReportResponse | None:
        report = self._records.get(report_id)
        if report is None or report.user_id != user_id:
            return None
        return report

    def clear(self) -> None:
        self._records.clear()


class SqlAlchemyReportRepository(ReportRepository):
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create(self, report: ReportResponse) -> ReportResponse:
        with self._session_factory() as session:
            session.add(_to_model(report))
            session.commit()
        return report

    def list(self, *, user_id: str) -> list[ReportResponse]:
        with self._session_factory() as session:
            rows = (
                session.query(ReportModel)
                .filter(ReportModel.user_id == user_id)
                .order_by(ReportModel.created_at.desc())
                .all()
            )
            return [_to_schema(row) for row in rows]

    def get(self, report_id: str, *, user_id: str) -> ReportResponse | None:
        with self._session_factory() as session:
            row = (
                session.query(ReportModel)
                .filter(ReportModel.id == report_id, ReportModel.user_id == user_id)
                .one_or_none()
            )
            return None if row is None else _to_schema(row)


def _to_model(report: ReportResponse) -> ReportModel:
    sections = to_json_safe([section.model_dump(mode="python") for section in report.sections])
    evidence = to_json_safe([item.model_dump(mode="python") for item in report.evidence])
    memo_meta = to_json_safe(report.memo_metadata.model_dump(mode="python"))
    return ReportModel(
        id=report.id,
        user_id=report.user_id,
        title=report.title,
        report_type=report.report_type.value,
        conversation_id=report.conversation_id,
        source_response_id=report.source_response_id,
        ticker=report.ticker,
        status=report.status.value,
        sections=sections if isinstance(sections, list) else [],
        evidence=evidence if isinstance(evidence, list) else [],
        citations=list(report.citations),
        memo_metadata=memo_meta if isinstance(memo_meta, dict) else {},
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _to_schema(model: ReportModel) -> ReportResponse:
    return ReportResponse(
        id=model.id,
        user_id=model.user_id,
        title=model.title,
        report_type=ReportType(model.report_type),
        conversation_id=model.conversation_id,
        source_response_id=model.source_response_id,
        ticker=model.ticker,
        status=ReportStatus(model.status),
        sections=[ReportSection.model_validate(item) for item in model.sections],
        evidence=[EvidenceItem.model_validate(item) for item in model.evidence],
        citations=list(model.citations),
        memo_metadata=ReportGenerationMeta.model_validate(model.memo_metadata or {}),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
