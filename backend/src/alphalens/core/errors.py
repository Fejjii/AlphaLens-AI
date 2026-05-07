"""Application error hierarchy and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from alphalens.core.logging import get_logger
from alphalens.schemas.common import ErrorResponse
from alphalens.services.plan_service import PlanAccessError

log = get_logger(__name__)


class AppError(Exception):
    """Base class for domain errors that map to a controlled HTTP response."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(self, message: str, *, code: str | None = None, details: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationFailedError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_failed"


class UpstreamError(AppError):
    """Errors caused by an external dependency (LLM, broker, market data)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_error"


def _error_response(status_code: int, code: str, message: str, details: object | None = None) -> JSONResponse:
    payload = ErrorResponse(code=code, message=message, details=details)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    log.warning("app_error", code=exc.code, message=exc.message)
    return _error_response(exc.status_code, exc.code, exc.message, details=exc.details)


async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    log.info("validation_error", errors=exc.errors())
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_failed",
        "Request validation failed.",
        details=exc.errors(),
    )


async def _plan_access_handler(_: Request, exc: PlanAccessError) -> JSONResponse:
    log.info(
        "quota_exceeded",
        error="quota_exceeded",
        feature=exc.feature,
        plan=exc.plan,
        limit=exc.limit,
        used=exc.used,
    )
    detail = {
        "error": "quota_exceeded",
        "feature": exc.feature,
        "plan": exc.plan,
        "limit": exc.limit,
        "used": exc.used,
        "reset_at": exc.reset_at,
        "message": exc.message,
    }
    return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": detail})


async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", error=str(exc))
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(PlanAccessError, _plan_access_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
