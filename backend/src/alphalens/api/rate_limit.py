"""Rate limiting backends and helpers."""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import Request, status

from alphalens.core.config import Settings
from alphalens.core.errors import AppError
from alphalens.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitExceeded(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limit_exceeded"

    def __init__(self, message: str, *, retry_after_seconds: int | None = None) -> None:
        details = {"retry_after_seconds": retry_after_seconds} if retry_after_seconds is not None else None
        super().__init__(message, details=details)


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int | None = None


class RateLimiter(Protocol):
    def check(self, *, route: str, subject: str) -> RateLimitResult: ...


class MemoryRateLimiter(RateLimiter):
    def __init__(self, *, limits: dict[str, int], window_seconds: int) -> None:
        self._limits = limits
        self._window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, *, route: str, subject: str) -> RateLimitResult:
        limit = self._limits.get(route)
        if limit is None:
            return RateLimitResult(True)
        key = f"{route}:{subject}"
        now = time.time()
        q = self._events[key]
        while q and now - q[0] >= self._window_seconds:
            q.popleft()
        if len(q) >= limit:
            retry_after = int(self._window_seconds - (now - q[0])) if q else self._window_seconds
            return RateLimitResult(False, max(retry_after, 1))
        q.append(now)
        return RateLimitResult(True)

    def clear(self) -> None:
        self._events.clear()


class RedisRateLimiter(RateLimiter):
    def __init__(
        self,
        *,
        redis_url: str,
        limits: dict[str, int],
        window_seconds: int,
        fail_open: bool = False,
    ) -> None:
        self._limits = limits
        self._window_seconds = window_seconds
        self._fail_open = fail_open
        try:
            import redis

            self._client = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        except Exception as exc:
            logger.warning("rate_limit_redis_init_failed", error=str(exc))
            self._client = None

    def check(self, *, route: str, subject: str) -> RateLimitResult:
        limit = self._limits.get(route)
        if limit is None:
            return RateLimitResult(True)
        if self._client is None:
            if self._fail_open:
                return RateLimitResult(True)
            raise RateLimitExceeded("Rate limiting unavailable.")
        key = self._key(route, subject)
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            count, ttl = pipe.execute()
            if int(count) == 1:
                self._client.expire(key, self._window_seconds)
                ttl = self._window_seconds
            if int(count) > limit:
                retry_after = int(ttl) if int(ttl) > 0 else self._window_seconds
                return RateLimitResult(False, retry_after)
            return RateLimitResult(True)
        except Exception as exc:
            logger.warning("rate_limit_redis_failed", error=str(exc))
            if self._fail_open:
                return RateLimitResult(True)
            raise RateLimitExceeded("Rate limiting unavailable.")

    def _key(self, route: str, subject: str) -> str:
        digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:16]
        return f"alphalens:rate_limit:{route}:{digest}"


def build_rate_limiter(settings: Settings) -> RateLimiter:
    limits = {
        "auth_login": settings.rate_limit_auth_login,
        "auth_register": settings.rate_limit_auth_register,
        "chat": settings.rate_limit_chat,
        "speech": settings.rate_limit_speech,
        "reports": settings.rate_limit_reports,
        "scenarios": settings.rate_limit_scenarios,
        "feedback": settings.rate_limit_feedback,
    }
    if settings.rate_limit_backend == "redis":
        redis_url = settings.rate_limit_redis_url or settings.redis_url
        if redis_url:
            return RedisRateLimiter(
                redis_url=redis_url,
                limits=limits,
                window_seconds=settings.rate_limit_window_seconds,
                fail_open=settings.app_env in {"dev", "test"},
            )
        if settings.app_env == "prod":
            raise RuntimeError("Redis rate limiting requested but no Redis URL is configured.")
    return MemoryRateLimiter(limits=limits, window_seconds=settings.rate_limit_window_seconds)


def rate_limit_request(request: Request, *, route: str, subject: str, settings: Settings) -> None:
    limiter: RateLimiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:
        limiter = build_rate_limiter(settings)
        request.app.state.rate_limiter = limiter
    result = limiter.check(route=route, subject=subject)
    if not result.allowed:
        raise RateLimitExceeded("Too many requests. Please try again later.", retry_after_seconds=result.retry_after_seconds)


def ip_subject(request: Request) -> str:
    return request.client.host if request.client else "unknown"

