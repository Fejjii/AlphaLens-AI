"""Lightweight language heuristics for multilingual chat."""

from __future__ import annotations

import re

_GERMAN_KEYWORDS = (" und ", " der ", " die ", " das ", " ist ", " nicht ", " mit ")
_FRENCH_KEYWORDS = (" et ", " le ", " la ", " les ", " est ", " pas ", " avec ")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")


def detect_language(text: str) -> str | None:
    lowered = f" {text.lower()} "
    if _ARABIC_RE.search(text):
        return "ar"
    if sum(keyword in lowered for keyword in _GERMAN_KEYWORDS) >= 2:
        return "de"
    if sum(keyword in lowered for keyword in _FRENCH_KEYWORDS) >= 2:
        return "fr"
    ascii_letters = sum(ch.isalpha() for ch in text if ch.isascii())
    if ascii_letters:
        return "en"
    return None


def get_response_language(
    user_text: str,
    user_preference: str = "auto",
    *,
    default_language: str = "en",
) -> str:
    if user_preference != "auto":
        return user_preference
    detected = detect_language(user_text)
    return detected or default_language
