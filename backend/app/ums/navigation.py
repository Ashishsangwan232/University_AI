"""Ranking of candidate "attendance" controls on a UMS page.

Playwright-free so it can be unit tested. A UMS dashboard contains several
controls whose text says "attendance" — event/QR attendance on a different
subdomain, biometric marking, correction requests — and clicking the wrong one
navigates the student's session away from the portal. This module decides which
one is worth clicking, before anything is clicked.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings

#: A stat tile such as "ATTENDANCE : 97%" whose click handler loads the real
#: attendance panel. On LPU UMS this is #AttPercent -> getAtt().
PERCENT_TILE = re.compile(r"attendance\s*[:\-]?\s*\d{1,3}\s*%")

#: Phrases that identify the real course-wise attendance page.
GOOD_PHRASES: list[tuple[str, int]] = [
    ("attendance summary", 7),
    ("course wise attendance", 7),
    ("coursewise attendance", 7),
    ("my attendance", 5),
    ("attendance detail", 5),
    ("view attendance", 4),
    ("attendance report", 4),
    ("attendance record", 4),
]


def host_of(url: str | None) -> str:
    try:
        return (urlparse(url or "").hostname or "").lower()
    except ValueError:
        return ""


def score_candidate(item: dict[str, Any]) -> int:
    """Rank one control. A score below ``UMS_MIN_CANDIDATE_SCORE`` is never clicked."""
    text = (item.get("text") or "").strip().lower()
    href = (item.get("href") or "").strip()
    onclick = (item.get("onclick") or "").lower()
    element_id = (item.get("id") or "").lower()
    hay = f"{text} {href.lower()} {onclick} {element_id}"

    score = 0
    for phrase, weight in GOOD_PHRASES:
        if phrase in hay:
            score += weight
    if text == "attendance":
        score += 4
    elif text.startswith("attendance"):
        score += 3

    for bad in settings.ums_attendance_block_words_list:
        if bad and bad in hay:
            score -= 9

    # An absolute link to another hostname is not the in-portal attendance page.
    if href.lower().startswith(("http://", "https://")) and settings.ums_host not in host_of(href):
        score -= 15

    if "__dopostback" in f"{href.lower()}{onclick}":
        score += 2
    if item.get("tag") == "a":
        score += 1

    # A control that runs a script to load an attendance panel in place. This is
    # how LPU UMS works: the dashboard tile #AttPercent calls getAtt(), which
    # fetches the attendance table by AJAX. Before that click no table exists
    # anywhere in the DOM, which is why nothing could be found by URL alone.
    if onclick and ("attend" in onclick or "attend" in element_id):
        score += 4
    if PERCENT_TILE.search(text):
        score += 3

    if not item.get("visible", True):
        score -= 4
    return score


def rank_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score every item in place and return them best-first.

    Visibility outranks score: Playwright cannot click a hidden element, and a
    UMS dashboard is full of high-scoring controls that live inside a closed
    modal or a collapsed menu. Those are reported but never clicked - opening
    the menu is what makes them real.
    """
    for item in items:
        item["score"] = score_candidate(item)
    return sorted(items, key=lambda i: (bool(i.get("visible")), i["score"]), reverse=True)
