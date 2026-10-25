"""University facts we store ourselves, in data/university_info.md.

The file is read once and kept in memory. A question is matched against each
"## " section by keyword - no crawler, no embeddings, no vector store. To change
what the bot knows, edit the file and restart the backend.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[1]

STOP_WORDS = {
    "a", "an", "and", "are", "at", "be", "can", "do", "does", "for", "from", "how", "i",
    "in", "is", "it", "lpu", "me", "much", "my", "of", "on", "or", "the", "there", "to",
    "university", "what", "when", "where", "which", "who", "will", "with", "you", "your",
    "about", "tell", "give", "please", "get", "know",
}


def _path() -> Path:
    path = Path(settings.university_info_file)
    return path if path.is_absolute() else BACKEND_DIR / path


def _words(text: str) -> list[str]:
    found = re.findall(r"[a-z0-9]+", text.lower())
    # "fees" should match "fee", "hostels" should match "hostel".
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in found if w not in STOP_WORDS]


@lru_cache(maxsize=1)
def sections() -> list[dict[str, Any]]:
    """The file split into its "## " sections. Empty if the file is missing."""
    path = _path()
    if not path.exists():
        return []
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    result = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        body = body.strip()
        source = ""
        match = re.search(r"^Source:\s*(.+)$", body, flags=re.M)
        if match:
            source = match.group(1).strip()
        result.append({
            "section": heading.strip(),
            "text": body,
            "source": source,
            "_heading_words": set(_words(heading)),
            "_body_words": set(_words(body)),
        })
    return result


def search(query: str, limit: int = 3) -> dict[str, Any]:
    """The sections that best match a question, best first."""
    every = sections()
    if not every:
        return {
            "available": False,
            "message": f"The university information file was not found at {_path()}.",
        }

    wanted = set(_words(query))
    scored = []
    for item in every:
        # A word in the heading counts three times as much as one in the text.
        score = 3 * len(wanted & item["_heading_words"]) + len(wanted & item["_body_words"])
        if score:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = [
        {"section": item["section"], "text": item["text"], "source": item["source"]}
        for _, item in scored[:limit]
    ]
    return {
        "available": True,
        "results": results,
        "all_sections": [item["section"] for item in every],
        "guidance": (
            "Answer only from these results and mention the source. If they do not "
            "contain the specific detail asked for, say it is not in CampusAI's stored "
            "information and suggest the relevant contact from the results."
            if results else
            "Nothing matched. If one of all_sections looks relevant, call again with "
            "its name; otherwise say this is not in CampusAI's stored information."
        ),
    }
