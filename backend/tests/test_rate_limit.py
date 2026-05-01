from __future__ import annotations

from dataclasses import dataclass

from fastapi import status

from alphalens.api.rate_limit import MemoryRateLimiter, RateLimitExceeded, build_rate_limiter, rate_limit_request
from alphalens.core.config import Settings
from alphalens.core.errors import AppError
from alphalens.api.rate_limit import ip_subject


def test_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = MemoryRateLimiter(limits={"chat": 2}, window_seconds=60)
    assert limiter.check(route="chat", subject="usr_1").allowed
    assert limiter.check(route="chat", subject="usr_1").allowed
    result = limiter.check(route="chat", subject="usr_1")
    assert result.allowed is False
    assert result.retry_after_seconds is not None


def test_memory_rate_limiter_keys_by_subject() -> None:
    limiter = MemoryRateLimiter(limits={"chat": 1}, window_seconds=60)
    assert limiter.check(route="chat", subject="usr_1").allowed
    assert limiter.check(route="chat", subject="usr_2").allowed


def test_build_rate_limiter_defaults_to_memory() -> None:
    limiter = build_rate_limiter(Settings())
    assert isinstance(limiter, MemoryRateLimiter)


def test_rate_limit_exception_shape() -> None:
    exc = RateLimitExceeded("Too many requests.", retry_after_seconds=15)
    assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert exc.details == {"retry_after_seconds": 15}


def test_ip_subject_handles_missing_client() -> None:
    @dataclass
    class DummyRequest:
        client: object | None = None

    assert ip_subject(DummyRequest()) == "unknown"
