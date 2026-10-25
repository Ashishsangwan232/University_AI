"""Cut a page into passages worth retrieving.

The old chunker sliced on a word count, so a passage regularly began mid-sentence
and ended mid-table, and nothing in it said which section of the site it came
from. This one cuts on the page's own structure and keeps the heading trail, so
a retrieved passage reads as "Hostel > Fees > ..." rather than as an anonymous
900 words.

Pure text in, pure text out - no network, no model, fully testable.
"""
from __future__ import annotations

import re
from typing import Any

#: A line that is a heading rather than prose: short, no full stop, and either
#: title case or the sort of label a CMS emits.
HEADING = re.compile(r"^[A-Z0-9][^.!?]{2,80}$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
#: Lines that carry nothing: lone bullets, stray punctuation, page numbers.
NOISE = re.compile(r"^[\s•·\-–—|>*_]+$|^\d{1,3}$")


def _is_heading(line: str, next_line: str | None) -> bool:
    text = line.strip()
    if not 3 <= len(text) <= 80 or not HEADING.match(text):
        return False
    if text.endswith((":", "?")):
        return True
    words = text.split()
    if len(words) > 12:
        return False
    # A heading is followed by prose, not by another fragment.
    return bool(next_line and len(next_line.strip()) > 40)


def split_sections(text: str) -> list[tuple[str, str]]:
    """Split page text into ``(heading, body)`` pairs in reading order."""
    lines = [line.strip() for line in (text or "").split("\n")]
    lines = [line for line in lines if line and not NOISE.match(line)]

    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current: list[str] = []
    for index, line in enumerate(lines):
        following = lines[index + 1] if index + 1 < len(lines) else None
        if _is_heading(line, following):
            if current:
                sections.append((current_heading, current))
            current_heading, current = line.rstrip(":"), []
        else:
            current.append(line)
    if current:
        sections.append((current_heading, current))
    return [(heading, "\n".join(body).strip()) for heading, body in sections if body]


def _pack(body: str, size: int, overlap: int) -> list[str]:
    """Fill passages up to ``size`` characters, breaking between sentences."""
    pieces = [piece.strip() for piece in SENTENCE_END.split(body) if piece.strip()]
    passages: list[str] = []
    current = ""
    for piece in pieces:
        if len(piece) > size:
            # One enormous sentence (a table flattened into a line). Cut it on
            # whitespace rather than dropping it.
            if current:
                passages.append(current)
                current = ""
            for start in range(0, len(piece), size):
                passages.append(piece[start:start + size].strip())
            continue
        if current and len(current) + len(piece) + 1 > size:
            passages.append(current)
            tail = current[-overlap:] if overlap else ""
            # Carry the tail of the previous passage so a fact split across the
            # boundary is still findable from either side.
            current = (tail + " " + piece).strip() if tail else piece
        else:
            current = f"{current} {piece}".strip()
    if current:
        passages.append(current)
    return [passage for passage in passages if len(passage) >= 40]


def chunk_page(
    page: dict[str, Any], size: int = 1000, overlap: int = 150
) -> list[dict[str, Any]]:
    """Turn one crawled page into retrievable chunks.

    ``page`` needs ``url``, ``title`` and ``text``; ``description`` is optional.
    Each chunk carries the page title and its own heading, so the model can say
    where an answer came from.
    """
    url = page.get("url", "")
    title = (page.get("title") or "").strip()
    description = (page.get("description") or "").strip()

    chunks: list[dict[str, Any]] = []
    for heading, body in split_sections(page.get("text") or ""):
        for passage in _pack(body, size, overlap):
            trail = " > ".join(part for part in (title, heading) if part)
            chunks.append({
                "url": url,
                "title": title,
                "heading": heading,
                "trail": trail,
                # What gets embedded and searched: the passage, prefixed by
                # where it sits, so "fees" matches a fees section even when the
                # passage itself only says "45,000 per year".
                "content": f"{trail}\n{passage}" if trail else passage,
                "passage": passage,
            })

    if not chunks and description:
        chunks.append({
            "url": url, "title": title, "heading": "", "trail": title,
            "content": f"{title}\n{description}" if title else description,
            "passage": description,
        })

    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
    return chunks


def chunk_pages(pages: list[dict[str, Any]], size: int = 1000, overlap: int = 150) -> list[dict[str, Any]]:
    everything: list[dict[str, Any]] = []
    for page in pages:
        everything.extend(chunk_page(page, size=size, overlap=overlap))
    return everything
