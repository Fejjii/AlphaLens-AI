"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from alphalens.api.deps import SettingsDep
from alphalens.schemas.common import HealthStatus

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def get_health(settings: SettingsDep) -> HealthStatus:
    return HealthStatus(
        status="ok",
        version=settings.app_version,
        environment=settings.app_env,
    )
