"""Report repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from alphalens.schemas.report import ReportResponse


class ReportRepository(Protocol):
    def create(self, report: ReportResponse) -> ReportResponse: ...

    def list(self) -> list[ReportResponse]: ...

    def get(self, report_id: str) -> ReportResponse | None: ...


@dataclass(slots=True)
class InMemoryReportRepository(ReportRepository):
    _records: dict[str, ReportResponse] = field(default_factory=dict)

    def create(self, report: ReportResponse) -> ReportResponse:
        self._records[report.id] = report
        return report

    def list(self) -> list[ReportResponse]:
        return sorted(self._records.values(), key=lambda item: item.created_at, reverse=True)

    def get(self, report_id: str) -> ReportResponse | None:
        return self._records.get(report_id)

    def clear(self) -> None:
        self._records.clear()
