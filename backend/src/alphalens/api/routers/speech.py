"""Speech transcription endpoint."""

from __future__ import annotations

import math
import uuid
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from alphalens.api.deps import CurrentUserDep, PlanServiceDep, SpeechServiceDep, UsageServiceDep
from alphalens.api.rate_limit import rate_limit_request
from alphalens.core.config import Settings, get_settings
from alphalens.core.logging import get_logger
from alphalens.integrations.speech.openai_speech_client import (
    build_openai_audio_filename,
    normalize_audio_content_type,
)
from alphalens.integrations.speech.base import SpeechError
from alphalens.schemas.speech import (
    SPEECH_DEMO_TRANSCRIPT,
    SPEECH_FALLBACK_REASON_NO_API_KEY,
    SPEECH_FALLBACK_REASON_SPEECH_DISABLED,
    SPEECH_FALLBACK_TRANSCRIBE_MESSAGE,
    SpeechCapabilities,
    TranscriptionResult,
)

router = APIRouter(prefix="/speech", tags=["speech"])
log = get_logger(__name__)

_SUPPORTED_MIME_TYPES = (
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/mpeg",
    "audio/mp4",
)
_SUPPORTED_MIME_TYPES_WITH_ALIASES = (
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
)
_SUPPORTED_LANGUAGES = ("en", "de", "fr", "ar")


def _normalize_mime_type(raw_mime_type: str | None) -> str | None:
    return normalize_audio_content_type(raw_mime_type)


def _speech_provider_mode(settings: Settings) -> Literal["real", "fallback"]:
    if settings.speech_enabled and bool(settings.openai_api_key):
        return "real"
    return "fallback"


def _capabilities_message(settings: Settings) -> str:
    if not settings.speech_enabled:
        return SPEECH_FALLBACK_REASON_SPEECH_DISABLED
    if not settings.openai_api_key:
        return SPEECH_FALLBACK_TRANSCRIBE_MESSAGE
    return (
        "Microphone and upload transcription use OpenAI speech-to-text when your plan allows speech uploads."
    )


def _speech_fallback_transcription_result(*, settings: Settings, request_id: str) -> TranscriptionResult:
    reason = (
        SPEECH_FALLBACK_REASON_SPEECH_DISABLED
        if not settings.speech_enabled
        else SPEECH_FALLBACK_REASON_NO_API_KEY
    )
    return TranscriptionResult(
        request_id=request_id,
        transcript="",
        detected_language="unknown",
        response_language="en",
        provider_mode="fallback",
        confidence=0.0,
        fallback_reason=reason,
        demo_transcript=SPEECH_DEMO_TRANSCRIPT,
        message=SPEECH_FALLBACK_TRANSCRIBE_MESSAGE,
        fallback_used=True,
        openai_called=False,
        openai_response_received=False,
    )


def _log_transcribe_dev(
    *,
    settings: Settings,
    payload: dict[str, Any],
) -> None:
    if settings.app_env != "dev":
        return
    log.debug("speech_transcribe_trace", **payload)


@router.get("/capabilities", response_model=SpeechCapabilities)
def capabilities(request: Request) -> SpeechCapabilities:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="App settings unavailable.")
    provider_mode = _speech_provider_mode(settings)
    max_upload_mb = math.ceil(settings.speech_max_upload_bytes / (1024 * 1024))
    openai_key_configured = bool(settings.openai_api_key)
    microphone_transcription_available = provider_mode == "real"
    return SpeechCapabilities(
        supported_mime_types=list(_SUPPORTED_MIME_TYPES_WITH_ALIASES),
        max_upload_mb=max_upload_mb,
        supported_languages=list(_SUPPORTED_LANGUAGES),
        provider_mode=provider_mode,
        openai_key_configured=openai_key_configured,
        microphone_transcription_available=microphone_transcription_available,
        message=_capabilities_message(settings),
    )


@router.post("/transcribe", response_model=TranscriptionResult)
async def transcribe(
    service: SpeechServiceDep,
    request: Request,
    current_user: CurrentUserDep,
    plans: PlanServiceDep,
    usage: UsageServiceDep,
    file: UploadFile = File(...),  # noqa: B008
    frontend_created_filename: str | None = Form(default=None),
) -> TranscriptionResult:
    request_id = str(uuid.uuid4())
    external_request_id = request.headers.get("x-request-id")
    rate_limit_request(request, route="speech", subject=current_user.id, settings=get_settings())
    settings = request.app.state.settings
    if not isinstance(settings, Settings):  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="App settings unavailable.")

    error_type: str | None = None
    error_message: str | None = None
    openai_called = False
    openai_response_received = False
    fallback_used = False
    transcript_preview = ""
    provider_mode = _speech_provider_mode(settings)
    speech_client_class = service.speech_client_class_name

    if file is None or not (file.filename or "").strip():
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": None,
                "received_content_type": None,
                "normalized_content_type": None,
                "received_file_size_bytes": None,
                "fallback_used": False,
                "openai_called": False,
                "openai_response_received": False,
                "transcript_preview": "",
                "error_type": "missing_audio_file",
                "error_message": "Missing multipart file",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "missing_audio_file", "hint": "Attach an audio file as multipart form field 'file'."},
        )

    normalized_content_type = _normalize_mime_type(file.content_type)
    raw_name = file.filename or "audio"
    file_bytes = await file.read()
    size_bytes = len(file_bytes)
    first_16_bytes_hex = file_bytes[:16].hex()
    openai_file_name_sent = build_openai_audio_filename(
        content_type=normalized_content_type,
        upload_filename=frontend_created_filename or raw_name,
    )
    openai_content_type_sent = normalized_content_type

    if normalized_content_type is None:
        error_type = "unsupported_audio_type"
        error_message = f"type={file.content_type or ''}"
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": raw_name,
                "received_upload_filename": raw_name,
                "received_content_type": file.content_type,
                "received_upload_content_type": file.content_type,
                "normalized_content_type": None,
                "received_file_size_bytes": size_bytes,
                "received_upload_size_bytes": size_bytes,
                "first_16_bytes_hex": first_16_bytes_hex,
                "frontend_created_filename": frontend_created_filename,
                "openai_file_name_sent": openai_file_name_sent,
                "openai_content_type_sent": openai_content_type_sent,
                "openai_model": "gpt-4o-mini-transcribe",
                "fallback_used": fallback_used,
                "openai_called": openai_called,
                "openai_response_received": openai_response_received,
                "transcript_preview": transcript_preview,
                "error_type": error_type,
                "error_message": error_message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "unsupported_audio_type",
                "received_content_type": file.content_type or "",
                "supported_content_types": list(_SUPPORTED_MIME_TYPES_WITH_ALIASES),
                "hint": "Browser microphone usually records audio/webm;codecs=opus.",
            },
        )

    if size_bytes == 0:
        error_type = "empty_audio_file"
        error_message = "Zero-byte upload"
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": raw_name,
                "received_upload_filename": raw_name,
                "received_content_type": file.content_type,
                "received_upload_content_type": file.content_type,
                "normalized_content_type": normalized_content_type,
                "received_file_size_bytes": size_bytes,
                "received_upload_size_bytes": size_bytes,
                "first_16_bytes_hex": first_16_bytes_hex,
                "frontend_created_filename": frontend_created_filename,
                "openai_file_name_sent": openai_file_name_sent,
                "openai_content_type_sent": openai_content_type_sent,
                "openai_model": "gpt-4o-mini-transcribe",
                "fallback_used": fallback_used,
                "openai_called": openai_called,
                "openai_response_received": openai_response_received,
                "transcript_preview": transcript_preview,
                "error_type": error_type,
                "error_message": error_message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "empty_audio_file",
                "hint": "Record or upload audio with content before transcription.",
            },
        )

    if size_bytes > settings.speech_max_upload_bytes:
        error_type = "audio_file_too_large"
        error_message = f"limit_bytes={settings.speech_max_upload_bytes}"
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": raw_name,
                "received_upload_filename": raw_name,
                "received_content_type": file.content_type,
                "received_upload_content_type": file.content_type,
                "normalized_content_type": normalized_content_type,
                "received_file_size_bytes": size_bytes,
                "received_upload_size_bytes": size_bytes,
                "first_16_bytes_hex": first_16_bytes_hex,
                "frontend_created_filename": frontend_created_filename,
                "openai_file_name_sent": openai_file_name_sent,
                "openai_content_type_sent": openai_content_type_sent,
                "openai_model": "gpt-4o-mini-transcribe",
                "fallback_used": fallback_used,
                "openai_called": openai_called,
                "openai_response_received": openai_response_received,
                "transcript_preview": transcript_preview,
                "error_type": error_type,
                "error_message": error_message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "audio_file_too_large",
                "max_upload_bytes": settings.speech_max_upload_bytes,
            },
        )

    if provider_mode == "fallback":
        fallback_used = True
        result = _speech_fallback_transcription_result(settings=settings, request_id=request_id)
        transcript_preview = ""
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": raw_name,
                "received_upload_filename": raw_name,
                "received_content_type": file.content_type,
                "received_upload_content_type": file.content_type,
                "normalized_content_type": normalized_content_type,
                "received_file_size_bytes": size_bytes,
                "received_upload_size_bytes": size_bytes,
                "first_16_bytes_hex": first_16_bytes_hex,
                "frontend_created_filename": frontend_created_filename,
                "openai_file_name_sent": openai_file_name_sent,
                "openai_content_type_sent": openai_content_type_sent,
                "openai_model": "gpt-4o-mini-transcribe",
                "fallback_used": True,
                "openai_called": False,
                "openai_response_received": False,
                "transcript_preview": transcript_preview,
                "error_type": None,
                "error_message": None,
            },
        )
        return result

    plans.ensure_usage_allowed(current_user, "speech_uploads")
    openai_called = True
    try:
        raw_result = service.transcribe_audio(
            file_bytes=file_bytes,
            filename=raw_name,
            content_type=normalized_content_type,
            request_id=request_id,
            frontend_created_filename=frontend_created_filename,
        )
        openai_response_received = True
        merged = raw_result.model_copy(
            update={
                "request_id": request_id,
                "fallback_used": False,
                "openai_called": True,
                "openai_response_received": True,
                "message": None,
                "demo_transcript": raw_result.demo_transcript,
            }
        )
        transcript_preview = (merged.transcript or "")[:240]
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": raw_name,
                "received_upload_filename": raw_name,
                "received_content_type": file.content_type,
                "received_upload_content_type": file.content_type,
                "normalized_content_type": normalized_content_type,
                "received_file_size_bytes": size_bytes,
                "received_upload_size_bytes": size_bytes,
                "first_16_bytes_hex": first_16_bytes_hex,
                "frontend_created_filename": frontend_created_filename,
                "openai_file_name_sent": openai_file_name_sent,
                "openai_content_type_sent": openai_content_type_sent,
                "openai_model": "gpt-4o-mini-transcribe",
                "fallback_used": False,
                "openai_called": True,
                "openai_response_received": True,
                "transcript_preview": transcript_preview,
                "error_type": None,
                "error_message": None,
            },
        )
        usage.record_event(
            event_type="speech_uploaded",
            provider=merged.provider_mode,
            user_id=current_user.id,
            metadata={"filename": raw_name},
        )
        return merged
    except SpeechError as exc:
        error_type = "SpeechError"
        error_message = str(exc)
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": raw_name,
                "received_upload_filename": raw_name,
                "received_content_type": file.content_type,
                "received_upload_content_type": file.content_type,
                "normalized_content_type": normalized_content_type,
                "received_file_size_bytes": size_bytes,
                "received_upload_size_bytes": size_bytes,
                "first_16_bytes_hex": first_16_bytes_hex,
                "frontend_created_filename": frontend_created_filename,
                "openai_file_name_sent": openai_file_name_sent,
                "openai_content_type_sent": openai_content_type_sent,
                "openai_model": "gpt-4o-mini-transcribe",
                "fallback_used": False,
                "openai_called": openai_called,
                "openai_response_received": False,
                "transcript_preview": transcript_preview,
                "error_type": error_type,
                "error_message": error_message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "speech_provider_unavailable",
                "request_id": request_id,
                "message": str(exc),
                "provider_mode": "real",
            },
        ) from exc
    except Exception as exc:
        error_type = exc.__class__.__name__
        error_message = str(exc)
        log.exception(
            "speech_transcription_unexpected_error",
            request_id=request_id,
            user_id=current_user.id,
            filename=raw_name,
            error=str(exc),
        )
        _log_transcribe_dev(
            settings=settings,
            payload={
                "request_id": request_id,
                "external_request_id": external_request_id,
                "endpoint": "/speech/transcribe",
                "provider_mode": provider_mode,
                "openai_key_configured": bool(settings.openai_api_key),
                "speech_client_class": speech_client_class,
                "received_file_name": raw_name,
                "received_upload_filename": raw_name,
                "received_content_type": file.content_type,
                "received_upload_content_type": file.content_type,
                "normalized_content_type": normalized_content_type,
                "received_file_size_bytes": size_bytes,
                "received_upload_size_bytes": size_bytes,
                "first_16_bytes_hex": first_16_bytes_hex,
                "frontend_created_filename": frontend_created_filename,
                "openai_file_name_sent": openai_file_name_sent,
                "openai_content_type_sent": openai_content_type_sent,
                "openai_model": "gpt-4o-mini-transcribe",
                "fallback_used": False,
                "openai_called": openai_called,
                "openai_response_received": False,
                "transcript_preview": transcript_preview,
                "error_type": error_type,
                "error_message": error_message,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "speech_transcription_failed",
                "request_id": request_id,
            },
        ) from exc
