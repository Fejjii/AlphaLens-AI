"""Reports and memo endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from alphalens.api.deps import ReportsServiceDep
from alphalens.schemas.report import ReportCreate, ReportResponse, ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse)
def create_report(payload: ReportCreate, service: ReportsServiceDep) -> ReportResponse:
    return service.create_report(payload)


@router.get("", response_model=list[ReportResponse])
def list_reports(service: ReportsServiceDep) -> list[ReportResponse]:
    return service.list_reports()


@router.get("/summary", response_model=ReportSummary)
def get_report_summary(service: ReportsServiceDep) -> ReportSummary:
    return service.summarize_reports()


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(report_id: str, service: ReportsServiceDep) -> ReportResponse:
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found.",
        )
    return report
