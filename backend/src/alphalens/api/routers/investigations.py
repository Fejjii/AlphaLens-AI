"""Investigation timeline endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from alphalens.api.deps import CurrentUserDep, InvestigationsServiceDep
from alphalens.schemas.investigation import (
    InvestigationRecord,
    InvestigationStatusUpdate,
)

router = APIRouter(prefix="/investigations", tags=["investigations"])


@router.get("", response_model=list[InvestigationRecord])
def list_investigations(
    service: InvestigationsServiceDep,
    current_user: CurrentUserDep,
) -> list[InvestigationRecord]:
    return service.list_investigations(user_id=current_user.id)


@router.get("/{investigation_id}", response_model=InvestigationRecord)
def get_investigation(
    investigation_id: str,
    service: InvestigationsServiceDep,
    current_user: CurrentUserDep,
) -> InvestigationRecord:
    record = service.get_investigation(investigation_id, user_id=current_user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")
    return record


@router.patch("/{investigation_id}/status", response_model=InvestigationRecord)
def update_investigation_status(
    investigation_id: str,
    payload: InvestigationStatusUpdate,
    service: InvestigationsServiceDep,
    current_user: CurrentUserDep,
) -> InvestigationRecord:
    record = service.update_status(
        investigation_id,
        user_id=current_user.id,
        status=payload.status,
    )
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")
    return record


@router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investigation(
    investigation_id: str,
    service: InvestigationsServiceDep,
    current_user: CurrentUserDep,
) -> None:
    deleted = service.delete_investigation(investigation_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found.")

