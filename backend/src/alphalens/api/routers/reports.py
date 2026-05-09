"""Reports and memo endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from alphalens.api.deps import CurrentUserDep, PlanServiceDep, ReportsServiceDep
from alphalens.api.rate_limit import rate_limit_request
from alphalens.core.config import get_settings
from alphalens.core.logging import get_logger
from alphalens.schemas.report import ReportCreate, ReportResponse, ReportSummary

log = get_logger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ReportResponse)
def create_report(
    request: Request,
    payload: ReportCreate,
    service: ReportsServiceDep,
    current_user: CurrentUserDep,
    plans: PlanServiceDep,
) -> ReportResponse:
    plans.ensure_usage_allowed(current_user, "reports")
    settings = get_settings()
    rate_limit_request(request, route="reports", subject=current_user.id, settings=settings)
    request_id = request.headers.get("x-request-id") or ""
    if settings.is_dev:
        mc = payload.memo_context
        log.info(
            "reports_create_post",
            request_id=request_id or None,
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            source_response_id=payload.source_response_id,
            report_type=payload.report_type.value,
            has_memo_context=mc is not None,
            memo_context_keys=list(mc.model_dump(exclude_none=True).keys()) if mc else [],
            ticker=payload.ticker,
        )
    return service.create_report(payload, user_id=current_user.id)


@router.get("", response_model=list[ReportResponse])
def list_reports(service: ReportsServiceDep, current_user: CurrentUserDep) -> list[ReportResponse]:
    return service.list_reports(user_id=current_user.id)


@router.get("/summary", response_model=ReportSummary)
def get_report_summary(
    service: ReportsServiceDep,
    current_user: CurrentUserDep,
) -> ReportSummary:
    return service.summarize_reports(user_id=current_user.id)


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    service: ReportsServiceDep,
    current_user: CurrentUserDep,
) -> ReportResponse:
    report = service.get_report(report_id, user_id=current_user.id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found.",
        )
    return report
