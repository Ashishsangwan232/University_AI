"""Tests for searching university_info.md (hybrid: meaning + keyword).

No browser, no network after the first run, no model API. The first run
downloads the free embedding model (~67 MB) into data/rag/models.

    python scripts/test_knowledge.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import knowledge  # noqa: E402
from app.agent.service import _info_answer as offline_info_answer  # noqa: E402
from app.core.config import settings  # noqa: E402

PASSED = 0
FAILED: list[str] = []

# Question -> a word that must appear in the top section's heading.
# Most of these share no keyword with the right section, so only search by
# meaning can find them.
FINDS = {
    "dorm rent": "hostel",
    "where do I see a doctor": "health",
    "someone is bullying me": "ragging",
    "how much is the mess food": "mess",
    "can I get financial aid": "scholarship",
    "phone number of registrar": "contact",
    "hostel fees": "hostel fees",
    "minimum attendance": "attendance",
    "exam dates": "calendar",
}
# Off-topic questions must return nothing, so the bot says it doesn't know.
NOTHING = ["who won the cricket world cup", "best pizza recipe", "what is the capital of France"]
# The offline agent searches every message, so small talk must not match there.
SMALL_TALK = ["hello", "hi there", "good morning", "thanks", "ok", "who are you"]


def top(query: str) -> str:
    results = knowledge.search(query)["results"]
    return results[0]["section"] if results else ""


def check(label: str, ok: bool, detail: str) -> None:
    global PASSED
    if ok:
        PASSED += 1
    else:
        FAILED.append(f"{label}: {detail}")


def main() -> int:
    method = knowledge.search_method()
    print(f"Search method: {method}")
    if method != "hybrid":
        print(f"Embeddings did not load ({knowledge._index['error']}); "
              "install fastembed: pip install fastembed")
        return 1

    for query, want in FINDS.items():
        got = top(query)
        check(query, want in got.lower(), f"top section was {got!r}, expected one about {want!r}")
        print(f"  {query:32s} -> {got}")
    for query in NOTHING:
        results = knowledge.search(query)["results"]
        check(query, not results, f"expected no match, got {[r['section'] for r in results]}")
        print(f"  {query:32s} -> {'(nothing)' if not results else results[0]['section']}")

    both = [r["section"] for r in knowledge.search("when do exams start")["results"][:2]]
    check("when do exams start", any("calendar" in s.lower() for s in both),
          f"academic calendar not in top 2: {both}")

    for text in SMALL_TALK:
        answer = offline_info_answer(text)
        check(f"offline: {text}", answer is None, f"matched {answer.answer[:40] if answer else ''!r}")
    for text in ("where do I see a doctor", "hostel fees"):
        check(f"offline: {text}", offline_info_answer(text) is not None, "no match")

    # Keyword-only mode still works when embeddings are switched off.
    settings.knowledge_embeddings = False
    knowledge._index.update(loaded=False, model=None, vectors=None, error="")
    check("keyword fallback", knowledge.search_method() == "keyword", "did not fall back")
    check("keyword: hostel fees", "hostel fees" in top("hostel fees").lower(), top("hostel fees"))

    print(f"\n{PASSED} passed, {len(FAILED)} failed")
    for line in FAILED:
        print("  FAIL", line)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
