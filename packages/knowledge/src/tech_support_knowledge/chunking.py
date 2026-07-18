"""Markdown chunking for handbook ingest.

Default strategy is ``page``: one chunk per source page (PDFs converted by
Docling carry a page-break marker). Oversized pages are windowed by
``max_chars``. Inputs without page markers (e.g. plain Markdown handbooks)
fall back to heading-based chunking so section context is preserved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Marker Docling inserts between pages (see ``_docling_worker``). Kept as an
#: HTML comment so it is invisible in rendered Markdown previews.
PAGE_BREAK_MARKER = "<!-- docling-page-break -->"

_HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class TextChunk:
    index: int
    section_title: str | None
    body: str
    page: int | None = None


def chunk_markdown(
    text: str,
    *,
    strategy: str = "page",
    max_chars: int = 4000,
    overlap_chars: int = 200,
    page_marker: str = PAGE_BREAK_MARKER,
) -> list[TextChunk]:
    """Chunk Markdown by page (default) or by heading.

    ``page`` strategy applies only when ``page_marker`` is present in the text;
    otherwise it falls back to heading-based chunking.
    """
    normalized = text.strip()
    if not normalized:
        return []

    if strategy == "page" and page_marker in text:
        return _chunk_by_page(
            text,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            page_marker=page_marker,
        )
    return _chunk_by_heading(normalized, max_chars=max_chars, overlap_chars=overlap_chars)


def _chunk_by_page(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int,
    page_marker: str,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    index = 0
    for page_number, raw_page in enumerate(text.split(page_marker), start=1):
        page = raw_page.strip()
        if not page:
            continue
        section_title = _first_heading(page) or f"Page {page_number}"
        for piece in _window(page, max_chars=max_chars, overlap_chars=overlap_chars):
            chunks.append(
                TextChunk(
                    index=index,
                    section_title=section_title,
                    body=piece,
                    page=page_number,
                )
            )
            index += 1
    return chunks


def _chunk_by_heading(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int,
) -> list[TextChunk]:
    sections = _split_by_headings(text)
    chunks: list[TextChunk] = []
    index = 0
    for section_title, body in sections:
        for piece in _window(body, max_chars=max_chars, overlap_chars=overlap_chars):
            chunks.append(TextChunk(index=index, section_title=section_title, body=piece))
            index += 1
    return chunks


def _first_heading(text: str) -> str | None:
    match = _HEADING.search(text)
    return match.group(2).strip() if match else None


def _split_by_headings(text: str) -> list[tuple[str | None, str]]:
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [(None, text)]

    sections: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append((None, preamble))

    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        block = f"{match.group(0).strip()}\n\n{body}".strip()
        sections.append((title, block))
    return sections


def _window(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return [p for p in pieces if p]
