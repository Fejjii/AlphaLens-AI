"""Markdown-aware chunking.

We split documents on top-level (`## `) headings to preserve semantic
boundaries, then further split overlong sections by paragraph. Heading
context is preserved on each chunk so retrieval results carry their
section title.

This is intentionally simple. Swap in a token-aware splitter (tiktoken)
once we wire up real embeddings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
DEFAULT_MAX_CHARS = 1200


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable unit of text."""

    text: str
    heading: str | None
    order: int


def chunk_markdown(content: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Split a markdown document into chunks.

    Args:
        content: Raw markdown text.
        max_chars: Soft upper bound per chunk. Sections larger than this
            are split on paragraph boundaries.

    Returns:
        Ordered list of `Chunk` objects.
    """

    sections = _split_by_heading(content)
    chunks: list[Chunk] = []
    order = 0
    for heading, body in sections:
        body = body.strip()
        if not body:
            continue
        for piece in _split_long(body, max_chars=max_chars):
            chunks.append(Chunk(text=piece, heading=heading, order=order))
            order += 1
    return chunks


def _split_by_heading(content: str) -> list[tuple[str | None, str]]:
    """Group lines under their nearest preceding heading."""

    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))

    return [(h, "\n".join(lines)) for h, lines in sections]


def _split_long(text: str, *, max_chars: int) -> list[str]:
    """Split a section by blank-line paragraphs if it exceeds `max_chars`."""

    if len(text) <= max_chars:
        return [text]

    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []
    buf: list[str] = []
    size = 0
    for para in paragraphs:
        if size + len(para) + 2 > max_chars and buf:
            pieces.append("\n\n".join(buf))
            buf, size = [], 0
        buf.append(para)
        size += len(para) + 2
    if buf:
        pieces.append("\n\n".join(buf))
    return pieces
