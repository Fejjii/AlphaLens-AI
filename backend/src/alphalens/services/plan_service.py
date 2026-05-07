"""Plan and quota enforcement service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from alphalens.core.config import Settings
from alphalens.schemas.plan import PlanCapabilities, PlanLimits, PlanName, PlanResponse, PlanUsage
from alphalens.schemas.user import UserProfile
from alphalens.services.usage_service import UsageService

PlanMetric = Literal["chats", "reports", "scenarios", "speech_uploads", "estimated_cost_usd"]
UsageEventKind = Literal["llm_call", "report_generated", "scenario_simulated", "speech_uploaded"]


@dataclass(frozen=True, slots=True)
class _PlanConfig:
    description: str
    limits: PlanLimits
    capabilities: PlanCapabilities


PLAN_REGISTRY: dict[PlanName, _PlanConfig] = {
    "free": _PlanConfig(
        description="Entry plan for evaluation and light usage.",
        limits=PlanLimits(
            monthly_chats=50,
            monthly_reports=5,
            monthly_scenarios=5,
            monthly_speech_uploads=5,
            monthly_estimated_cost_usd=10.0,
        ),
        capabilities=PlanCapabilities(
            tools=["portfolio", "risk", "rag"],
            models=["gpt-4o-mini"],
        ),
    ),
    "pro": _PlanConfig(
        description="For individual power users and analysts.",
        limits=PlanLimits(
            monthly_chats=500,
            monthly_reports=50,
            monthly_scenarios=50,
            monthly_speech_uploads=25,
            monthly_estimated_cost_usd=100.0,
        ),
        capabilities=PlanCapabilities(
            tools=["portfolio", "risk", "rag", "market_data", "search", "macro", "sec"],
            models=["gpt-4o-mini", "gpt-4o"],
        ),
    ),
    "team": _PlanConfig(
        description="For collaborative team workflows.",
        limits=PlanLimits(
            monthly_chats=5000,
            monthly_reports=500,
            monthly_scenarios=500,
            monthly_speech_uploads=200,
            monthly_estimated_cost_usd=1000.0,
        ),
        capabilities=PlanCapabilities(
            tools=["portfolio", "risk", "rag", "market_data", "search", "macro", "sec", "speech"],
            models=["gpt-4o-mini", "gpt-4o", "claude-3.5-sonnet"],
        ),
    ),
}


class PlanAccessError(Exception):
    """Raised when a plan quota would be exceeded; mapped to HTTP 429 by the API layer."""

    def __init__(
        self,
        message: str,
        *,
        feature: PlanMetric,
        plan: PlanName,
        limit: int | float | None,
        used: int | float,
        reset_at: str,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.feature = feature
        self.plan = plan
        self.limit = limit
        self.used = used
        self.reset_at = reset_at


class PlanService:
    def __init__(self, *, settings: Settings, usage_service: UsageService) -> None:
        self._settings = settings
        self._usage_service = usage_service

    def get_current_plan(self, user: UserProfile) -> PlanResponse:
        config = PLAN_REGISTRY[user.plan.value]
        return PlanResponse(
            plan=user.plan.value,
            limits=config.limits,
            capabilities=config.capabilities,
            description=config.description,
        )

    def list_plans(self) -> list[PlanResponse]:
        return [
            PlanResponse(plan=name, limits=config.limits, capabilities=config.capabilities, description=config.description)
            for name, config in PLAN_REGISTRY.items()
        ]

    def can_access_tool(self, user: UserProfile, tool_name: str) -> bool:
        return tool_name in PLAN_REGISTRY[user.plan.value].capabilities.tools

    def can_access_model(self, user: UserProfile, model_name: str) -> bool:
        return model_name in PLAN_REGISTRY[user.plan.value].capabilities.models

    def usage(self, user: UserProfile) -> PlanUsage:
        plan = self.get_current_plan(user)
        events = self._monthly_events(user)
        monthly_usage = {
            "chats": sum(1 for event in events if event.event_type in {"llm_call", "llm_fallback"}),
            "reports": sum(1 for event in events if event.event_type == "report_generated"),
            "scenarios": sum(1 for event in events if event.event_type == "scenario_simulated"),
            "speech_uploads": sum(1 for event in events if event.event_type == "speech_uploaded"),
            "estimated_cost_usd": round(
                sum(event.estimated_cost_usd or 0.0 for event in events), 8
            ),
        }
        remaining_quota = {
            "chats": _remaining(plan.limits.monthly_chats, monthly_usage["chats"]),
            "reports": _remaining(plan.limits.monthly_reports, monthly_usage["reports"]),
            "scenarios": _remaining(plan.limits.monthly_scenarios, monthly_usage["scenarios"]),
            "speech_uploads": _remaining(
                plan.limits.monthly_speech_uploads, monthly_usage["speech_uploads"]
            ),
            "estimated_cost_usd": _remaining(
                plan.limits.monthly_estimated_cost_usd, monthly_usage["estimated_cost_usd"]
            ),
        }
        return PlanUsage(
            plan=user.plan.value,
            monthly_usage=monthly_usage,
            remaining_quota=remaining_quota,
            limits=plan.limits,
            capabilities=plan.capabilities,
            current_month=_month_key(),
            quota_reset_at=_quota_reset_at_iso(),
        )

    def ensure_usage_allowed(self, user: UserProfile, metric: PlanMetric) -> None:
        if self._settings.app_env == "dev" and self._settings.dev_bypass_quotas:
            return
        plan = self.get_current_plan(user)
        usage = self.usage(user)
        limit = getattr(plan.limits, f"monthly_{metric}")
        used = usage.monthly_usage[metric]
        if limit is not None and used >= limit:
            reset_at = _quota_reset_at_iso()
            message = (
                f"Monthly {metric.replace('_', ' ')} limit reached for the {user.plan.value} plan."
            )
            raise PlanAccessError(
                message,
                feature=metric,
                plan=user.plan.value,
                limit=limit,
                used=used,
                reset_at=reset_at,
            )

    def remaining_quota(self, user: UserProfile) -> dict[str, int | float | None]:
        return self.usage(user).remaining_quota

    def _monthly_events(self, user: UserProfile):
        month = _month_key()
        events = self._usage_service.list_usage_events(user_id=user.id)
        return [
            event
            for event in events
            if event.created_at.strftime("%Y-%m") == month
        ]


def _remaining(limit: int | float | None, used: int | float) -> int | float | None:
    if limit is None:
        return None
    return max(limit - used, 0)


def _month_key() -> str:
    return datetime.now(tz=UTC).strftime("%Y-%m")


def _quota_reset_at_iso() -> str:
    """UTC instant when the current monthly quota window resets (first moment of next calendar month)."""
    now = datetime.now(tz=UTC)
    if now.month == 12:
        nxt = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        nxt = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return nxt.strftime("%Y-%m-%dT%H:%M:%SZ")

