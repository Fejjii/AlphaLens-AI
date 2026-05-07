"""Unit coverage for quota bypass flags (no HTTP)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alphalens.core.config import Settings
from alphalens.schemas.user import UserPlan, UserProfile, UserRole
from alphalens.services.plan_service import PlanAccessError, PlanService
from alphalens.services.usage_service import UsageService


@pytest.fixture
def quota_user() -> UserProfile:
    return UserProfile(
        id="usr_quota_unit",
        email="quota.unit@example.com",
        full_name="Quota Unit",
        role=UserRole.USER,
        plan=UserPlan.FREE,
        is_active=True,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def test_plan_service_skips_quotas_when_dev_bypass_enabled(
    quota_user: UserProfile,
) -> None:
    usage = UsageService()
    for _ in range(50):
        usage.record_event(
            event_type="speech_uploaded",
            provider="test",
            user_id=quota_user.id,
        )
    settings = Settings.model_construct(app_env="dev", dev_bypass_quotas=True)
    svc = PlanService(settings=settings, usage_service=usage)
    svc.ensure_usage_allowed(quota_user, "speech_uploads")


def test_plan_service_enforces_quotas_when_bypass_disabled(
    quota_user: UserProfile,
) -> None:
    usage = UsageService()
    for _ in range(5):
        usage.record_event(
            event_type="speech_uploaded",
            provider="test",
            user_id=quota_user.id,
        )
    settings = Settings.model_construct(app_env="dev", dev_bypass_quotas=False)
    svc = PlanService(settings=settings, usage_service=usage)
    with pytest.raises(PlanAccessError):
        svc.ensure_usage_allowed(quota_user, "speech_uploads")
