"""Speech transcription endpoint."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from alphalens.api.deps import SpeechServiceDep
from alphalens.core.config import Settings
from alphalens.schemas.speech import TranscriptionResult

router = APIRouter(prefix="/speech", tags=["speech"])

_ALLOWED_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/webm",
    "audio/ogg",
}


@router.post("/transcribe", response_model=TranscriptionResult)
async def transcribe(
    service: SpeechServiceDep,
    request: Request,
    file: UploadFile = File(...),
) -> TranscriptionResult:
    settings = request.app.state.settings
    if not isinstance(settings, Settings):  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="App settings unavailable.")
    if file.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio type. Allowed: wav, mp3, m4a, webm, ogg.",
        )
    file_bytes = await file.read()
    if len(file_bytes) > settings.speech_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is too large.",
        )
    return service.transcribe_audio(file_bytes=file_bytes, filename=file.filename or "audio")
