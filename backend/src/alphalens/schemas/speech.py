"""Schemas for speech-to-text integrations."""

from __future__ import annotations

from pydantic import Field

from alphalens.schemas.common import APIModel


class TranscriptionResult(APIModel):
    text: str = Field(..., min_length=1)
    language: str | None = None
    provider: str
    detected_language: str | None = None
