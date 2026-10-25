"""The college knowledge base: crawl the public site, then answer from it.

    ingest_website("https://www.lpu.in/")   -> crawl, chunk, embed, store
    search_knowledge("hostel fees")         -> ranked passages with their URLs

Everything the model is told about the college comes from here, and every
result carries the page it came from, so an answer can always be checked. When
a passage cannot be found the search says the knowledge base has nothing rather
than letting the model fill the gap.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.core.config import settings
from app.rag import store
from app.rag.chunker import chunk_pages
from app.rag.crawler import crawl_website
from app.rag.embeddings import (
    EmbeddingsUnavailable,
    describe as describe_embedder,
    embed_in_batches,
    get_embedder,
)
from app.rag.search import rank

log = logging.getLogger("campusai.rag")


def ingest_website(
    url: str | None = None,
    max_pages: int | None = None,
    max_depth: int | None = None,
) -> dict[str, Any]:
    """Crawl a site and replace whatever was stored for it before.

    Embedding failures do not fail the ingest: the pages are still stored and
    searched by keyword, and the result says so, because a keyword-searchable
    knowledge base is worth far more than a failed one.
    """
    target = (url or settings.college_website_url or "https://www.lpu.in/").strip()
    started = time.time()
    log.info("[RAG] Crawling %s (max %s pages, depth %s)", target,
             max_pages or settings.rag_crawl_max_pages,
             max_depth if max_depth is not None else settings.rag_crawl_max_depth)

    pages = crawl_website(target, max_pages=max_pages, max_depth=max_depth)
    if not pages:
        raise RuntimeError(
            f"No readable pages were found at {target}. Check the URL is reachable and that "
            "robots.txt does not disallow crawling."
        )

    chunks = chunk_pages(
        [page.__dict__ for page in pages],
        size=settings.rag_chunk_characters,
        overlap=settings.rag_chunk_overlap,
    )
    if not chunks:
        raise RuntimeError(f"{len(pages)} page(s) were fetched but none produced readable text.")

    vectors: list[list[float]] | None = None
    embedding_note = ""
    embedder = get_embedder()
    if embedder.name == "none":
        embedding_note = "No embedding provider configured, so search uses keywords only."
    else:
        try:
            vectors = embed_in_batches(embedder, [chunk["content"] for chunk in chunks])
        except EmbeddingsUnavailable as exc:
            vectors = None
            embedding_note = f"Stored without vectors - search will use keywords only. {exc}"
            log.warning("[RAG] %s", embedding_note)

    meta = store.replace_site(store.host_of(target), chunks, vectors)
    elapsed = round(time.time() - started, 1)
    log.info("[RAG] Ingested %d page(s) -> %d chunk(s) in %ss", len(pages), len(chunks), elapsed)

    return {
        "source_url": target,
        "pages": len(pages),
        "chunks": len(chunks),
        "embedded": bool(vectors),
        "embedding_provider": embedder.name,
        "embedding_model": embedder.model,
        "note": embedding_note,
        "seconds": elapsed,
        "store": meta,
        "sample_pages": [page.as_dict() for page in pages[:10]],
    }


def search_knowledge(query: str, limit: int | None = None) -> dict[str, Any]:
    """Ranked passages from the college website for one question."""
    limit = limit or settings.rag_top_k
    chunks, vectors = store.load()
    if not chunks:
        return {
            "query": query,
            "results": [],
            "available": False,
            "message": (
                "The college knowledge base is empty. Run "
                "`python scripts/ingest_site.py` (or POST /api/rag/ingest) to read "
                "the college website first."
            ),
        }

    query_vector: list[float] | None = None
    note = ""
    if vectors is not None:
        embedder = get_embedder()
        try:
            query_vector = embedder.embed_query(query)
        except EmbeddingsUnavailable as exc:
            note = f"Semantic search is unavailable, so this used keywords only. {exc}"
            log.info("[RAG] %s", note)

    results, method = rank(chunks, query, query_vector, vectors, limit)
    pages = len({chunk.get("url") for chunk in chunks if chunk.get("url")})

    if results:
        # Spelled out, because a model handed five relevant passages was still
        # replying "I have no information about that" and sending the student
        # off to the college website - which is the very thing it just read.
        guidance = (
            f"{len(results)} passage(s) from the college website matched. Answer from them "
            "and name the page. If they do not contain the exact figure or date asked for, "
            "say what the site DOES cover on the subject, give the page, and say that the "
            "specific detail is not published there - do not reply as though the knowledge "
            "base were empty, and do not tell the student to go and read the college "
            "website, because these passages are the college website."
        )
    else:
        guidance = (
            f"Nothing among the {pages} page(s) read from the college website matches this. "
            "Say that plainly - the site does not appear to cover it - rather than answering "
            "from memory or inventing a figure."
        )

    return {
        "query": query,
        "available": True,
        "results": results,
        "found": len(results),
        "method": method,
        "searched_chunks": len(chunks),
        "pages_indexed": pages,
        "guidance": guidance,
        "note": note,
        "message": "" if results else guidance,
    }


def knowledge_status() -> dict[str, Any]:
    """What has been ingested, and whether semantic search is working."""
    return {**store.stats(), "embeddings": describe_embedder(),
            "default_site": settings.college_website_url or "https://www.lpu.in/"}


def clear_knowledge() -> dict[str, Any]:
    return store.clear()
