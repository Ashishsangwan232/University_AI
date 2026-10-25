"""Ranking: keywords and meaning together.

Vectors alone are bad at exact terms - a query for "CSE329" or "hostel fee 2026"
wants the passage that literally contains those tokens. Keywords alone are bad
at paraphrase - "what do I pay to live on campus" shares no words with "hostel
charges". So both run, each is normalised to 0..1, and the scores are blended.

When no vectors exist (no embedder, or numpy missing) this degrades to BM25
alone and says so in the result, rather than returning nothing.

Pure functions over the loaded store: no network, no database.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from app.core.config import settings

TOKEN = re.compile(r"[a-z0-9]+")
#: Words too common in English or on a university site to help ranking.
STOPWORDS = frozenset("""
a an and are as at be but by for from has have how i in is it its of on or that
the to was what when where which who will with you your do does did can could
should would about into over under my me our we they their there here if then
than so such no not any all more most other some only own same too very just
university college lpu please kindly
""".split())


def tokenise(text: str) -> list[str]:
    return [token for token in TOKEN.findall((text or "").lower()) if token not in STOPWORDS]


def build_bm25(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """The document statistics BM25 needs, computed once per search."""
    documents = [tokenise(chunk.get("content", "")) for chunk in chunks]
    frequencies = [Counter(document) for document in documents]
    lengths = [len(document) for document in documents]
    average = (sum(lengths) / len(lengths)) if lengths else 0.0

    document_frequency: Counter[str] = Counter()
    for frequency in frequencies:
        document_frequency.update(frequency.keys())

    return {
        "frequencies": frequencies,
        "lengths": lengths,
        "average_length": average,
        "document_frequency": document_frequency,
        "count": len(documents),
    }


def bm25_scores(index: dict[str, Any], query: str, k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Okapi BM25, the standard keyword ranking, in about twenty lines."""
    terms = tokenise(query)
    count = index["count"]
    scores = [0.0] * count
    if not terms or not count:
        return scores

    average = index["average_length"] or 1.0
    for term in set(terms):
        appearances = index["document_frequency"].get(term, 0)
        if not appearances:
            continue
        # Smoothed inverse document frequency: a term in every page is worthless.
        idf = math.log(1 + (count - appearances + 0.5) / (appearances + 0.5))
        for position in range(count):
            frequency = index["frequencies"][position].get(term, 0)
            if not frequency:
                continue
            length = index["lengths"][position] or 1
            denominator = frequency + k1 * (1 - b + b * length / average)
            scores[position] += idf * (frequency * (k1 + 1)) / denominator
    return scores


def cosine_scores(
    vectors: Any, query_vector: list[float], candidates: list[int] | None = None
) -> list[float]:
    """Similarity against every stored row, or just the candidate rows.

    Stored rows are already unit length, so this is a dot product. With numpy
    the whole matrix is done at once; without it only the ``candidates`` are
    scored - a few hundred rows in Python is instant, where several thousand
    would not be.
    """
    if vectors is None or not query_vector:
        return []
    length = len(vectors)
    norm = math.sqrt(sum(value * value for value in query_vector))
    if not norm or not length:
        return []
    query = [value / norm for value in query_vector]

    if getattr(vectors, "fast", False):
        import numpy as np

        return (vectors.matrix @ np.asarray(query, dtype="float32")).tolist()

    scores = [0.0] * length
    for index in (candidates if candidates is not None else range(length)):
        scores[index] = sum(a * b for a, b in zip(vectors.row(index), query))
    return scores


def _scale_by_best(scores: list[float]) -> list[float]:
    """Divide by the best score, so zero still means "did not match".

    Min-max scaling would be wrong here: it forces the weakest *matching*
    passage to exactly 0, and the ranker then discards it as a non-match. On a
    small store that silently loses real answers.
    """
    highest = max(scores) if scores else 0.0
    if highest <= 0:
        return [0.0] * len(scores)
    return [max(0.0, score) / highest for score in scores]


def _spread(scores: list[float]) -> list[float]:
    """Min-max, for cosine - where every passage scores something and only the
    differences between them carry information."""
    if not scores:
        return []
    lowest, highest = min(scores), max(scores)
    if highest - lowest < 1e-9:
        return [0.0] * len(scores)
    return [(score - lowest) / (highest - lowest) for score in scores]


def _canonical(url: str) -> str:
    return (url or "").split("#")[0].rstrip("/").lower()


def _fingerprint(text: str) -> str:
    """Enough of a passage to recognise it again on a different page."""
    return " ".join(TOKEN.findall((text or "").lower()))[:220]


def rank(
    chunks: list[dict[str, Any]],
    query: str,
    query_vector: list[float] | None,
    vectors: Any,
    limit: int,
    vector_weight: float | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """The ranked results and the name of the method that produced them."""
    if not chunks:
        return [], "empty"

    raw_keyword = bm25_scores(build_bm25(chunks), query)
    keyword = _scale_by_best(raw_keyword)

    # Without numpy, score only the strongest keyword matches by meaning. It is
    # a rerank rather than a full vector search, and it keeps a 3,000-passage
    # store answering instantly on a machine that has no numpy installed.
    candidates: list[int] | None = None
    if vectors is not None and not getattr(vectors, "fast", False):
        ordered = sorted(range(len(chunks)), key=lambda index: raw_keyword[index], reverse=True)
        candidates = ordered[:settings.rag_rerank_candidates]

    semantic = _spread(cosine_scores(vectors, query_vector or [], candidates))

    if semantic and len(semantic) == len(chunks):
        weight = settings.rag_vector_weight if vector_weight is None else vector_weight
        combined = [
            weight * semantic[index] + (1 - weight) * keyword[index]
            for index in range(len(chunks))
        ]
        method = ("hybrid (meaning + keywords)" if candidates is None
                  else "keywords, reranked by meaning")
    else:
        combined = keyword
        method = "keywords only"

    order = sorted(range(len(chunks)), key=lambda index: combined[index], reverse=True)

    # At most one passage per page, so five results are five sources rather
    # than five slices of the same page.
    results: list[dict[str, Any]] = []
    seen_pages: set[str] = set()
    seen_text: set[str] = set()
    for index in order:
        if combined[index] <= 0:
            break
        chunk = chunks[index]
        page = _canonical(chunk.get("url", ""))
        if page in seen_pages:
            continue
        # Sites publish the same block under several URLs - LPU's two
        # international pages are word for word identical - so also skip a
        # passage whose text has already been shown, whatever its URL.
        fingerprint = _fingerprint(chunk.get("passage") or chunk.get("content", ""))
        if fingerprint and fingerprint in seen_text:
            continue
        seen_pages.add(page)
        seen_text.add(fingerprint)
        results.append({
            "title": chunk.get("title") or chunk.get("url", ""),
            "heading": chunk.get("heading", ""),
            "url": chunk.get("url", ""),
            "content": chunk.get("passage") or chunk.get("content", ""),
            "score": round(float(combined[index]), 4),
            "keyword_score": round(float(keyword[index]), 4),
            "semantic_score": round(float(semantic[index]), 4) if semantic else None,
        })
        if len(results) >= limit:
            break
    return results, method
