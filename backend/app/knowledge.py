"""University facts we store ourselves, in data/university_info.md.

The file is read once and kept in memory, split into its "## " sections. A
question is matched against those sections two ways (hybrid search):

* by meaning - a small embedding model (fastembed, BAAI/bge-small-en-v1.5)
  runs locally on the CPU, free, with no API key. "dorm rent" finds
  "Hostel fees" and "someone is bullying me" finds the anti-ragging section,
  even though they share no words;
* by keyword - exact words still count, so a code like "ICC" or a word in a
  section heading is never missed.

If the embedding model cannot load (package missing, first download failed,
or KNOWLEDGE_EMBEDDINGS=false) search quietly falls back to keywords alone.
No crawler, no vector database: 18 sections fit in memory as a small matrix.
To change what the bot knows, edit the file and restart the backend.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

log = logging.getLogger("campusai.agent")

BACKEND_DIR = Path(__file__).resolve().parents[1]

STOP_WORDS = {
    "a", "an", "and", "are", "at", "be", "can", "do", "does", "for", "from", "how", "i",
    "in", "is", "it", "lpu", "me", "much", "my", "of", "on", "or", "the", "there", "to",
    "university", "what", "when", "where", "which", "who", "will", "with", "you", "your",
    "about", "tell", "give", "please", "get", "know",
}

#: How much meaning counts against keywords in the final score.
SEMANTIC_WEIGHT = 0.7
#: Keyword score that earns the full keyword share: two words in a heading.
#: One stray body word ("see") then adds little, so it cannot outvote meaning.
KEYWORD_FULL_SCORE = 6


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else BACKEND_DIR / path


def _path() -> Path:
    return _resolve(settings.university_info_file)


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


# ------------------------------------------------------------ embeddings
_lock = threading.Lock()
_index: dict[str, Any] = {"loaded": False, "model": None, "vectors": None, "error": ""}


def _load_index() -> dict[str, Any]:
    """Load the embedding model and embed every section, once.

    The first run downloads the model (~67 MB) into data/rag/models; after
    that it works offline. Any failure leaves keyword search in charge.
    """
    with _lock:
        if _index["loaded"]:
            return _index
        _index["loaded"] = True
        if not settings.knowledge_embeddings:
            _index["error"] = "disabled in settings"
            return _index
        every = sections()
        if not every:
            return _index
        try:
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            import numpy as np
            from fastembed import TextEmbedding

            model = TextEmbedding(
                model_name=settings.knowledge_embedding_model,
                cache_dir=str(_resolve(settings.knowledge_embedding_dir) / "models"),
            )
            passages = [f"{item['section']}\n{item['text']}" for item in every]
            vectors = np.array(list(model.passage_embed(passages)))
            vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
            _index["model"], _index["vectors"] = model, vectors
            log.info("Knowledge search: %d sections embedded with %s",
                     len(every), settings.knowledge_embedding_model)
        except Exception as exc:  # noqa: BLE001 - any failure means keyword-only
            _index["error"] = f"{type(exc).__name__}: {exc}"
            log.warning("Knowledge search: embeddings unavailable, using keywords only (%s)",
                        _index["error"])
        return _index


def warm_up() -> None:
    """Load the model in the background at startup so the first question is fast."""
    threading.Thread(target=_load_index, name="knowledge-warm-up", daemon=True).start()


def _similarities(query: str) -> list[float] | None:
    """Cosine similarity of the query to each section, or None without embeddings."""
    index = _load_index()
    if index["model"] is None:
        return None
    import numpy as np

    vector = np.array(list(index["model"].query_embed([query])))[0]
    vector /= np.linalg.norm(vector)
    return (index["vectors"] @ vector).tolist()


def search_method() -> str:
    """'hybrid' when embeddings are loaded, otherwise 'keyword'."""
    return "hybrid" if _load_index()["model"] is not None else "keyword"


# ---------------------------------------------------------------- search
def search(query: str, limit: int = 3, min_similarity: float | None = None) -> dict[str, Any]:
    """The sections that best match a question, best first.

    ``min_similarity`` overrides KNOWLEDGE_MIN_SIMILARITY. The offline agent
    passes a stricter value because it searches every message, small talk
    included ("good morning" is ~0.59 to the Library section's "8:00 AM").
    """
    every = sections()
    if not every:
        return {
            "available": False,
            "message": f"The university information file was not found at {_path()}.",
        }

    wanted = set(_words(query))
    # A word in the heading counts three times as much as one in the text.
    keyword = [3 * len(wanted & item["_heading_words"]) + len(wanted & item["_body_words"])
               for item in every]
    similarity = _similarities(query) if query.strip() else None

    floor = settings.knowledge_min_similarity if min_similarity is None else min_similarity
    scored = []
    for i, item in enumerate(every):
        if similarity is None:
            score = float(keyword[i])
        else:
            # A section qualifies by meaning (above the floor) or by sharing a word.
            if similarity[i] < floor and not keyword[i]:
                continue
            meaning = max(0.0, (similarity[i] - floor) / (1 - floor))
            words = min(keyword[i], KEYWORD_FULL_SCORE) / KEYWORD_FULL_SCORE
            score = SEMANTIC_WEIGHT * meaning + (1 - SEMANTIC_WEIGHT) * words
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = [
        {"section": item["section"], "text": item["text"], "source": item["source"]}
        for _, item in scored[:limit]
    ]
    return {
        "available": True,
        "results": results,
        "search_method": "hybrid" if similarity is not None else "keyword",
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
