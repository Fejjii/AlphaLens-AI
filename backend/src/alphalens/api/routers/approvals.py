"""Approval workflow endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from alphalens.api.deps import ApprovalsServiceDep, CurrentUserDep
from alphalens.schemas.approval import ApprovalDecision, ApprovalRecord, ApprovalStatus

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalRecord])
def list_approvals(
    service: ApprovalsServiceDep,
    current_user: CurrentUserDep,
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
) -> list[ApprovalRecord]:
    return service.list_approvals(user_id=current_user.id, status=status_filter)


@router.get("/{approval_id}", response_model=ApprovalRecord)
def get_approval(
    approval_id: str,
    service: ApprovalsServiceDep,
    current_user: CurrentUserDep,
) -> ApprovalRecord:
    approval = service.get_approval(approval_id, user_id=current_user.id)
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval '{approval_id}' not found.",
        )
    return approval


@router.post("/{approval_id}/decision", response_model=ApprovalRecord)
def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    service: ApprovalsServiceDep,
    current_user: CurrentUserDep,
) -> ApprovalRecord:
    try:
        approval = service.decide_approval(approval_id, payload, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if approval is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval '{approval_id}' not found.",
        )
    return approval
