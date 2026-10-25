"""Turning text into vectors, without the whole feature failing when it can't.

Two things went wrong with the previous version, and both are fixed here:

  * it read ``OLLAMA_BASE_URL``, which now points at Ollama Cloud for chat. The
    embedding daemon is a separate, local thing, so it has its own setting;
  * any failure raised, so one unreachable daemon meant no knowledge base at
    all. Now an unavailable embedder degrades to keyword search, which is worse
    but is still an answer, and the search result says which one was used.

Providers: ``ollama`` (local, default), ``gemini``, ``none``.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from app.core.config import settings

log = logging.getLogger("campusai.rag")


class EmbeddingsUnavailable(RuntimeError):
    """Raised when no embedder can be reached. Callers fall back to keywords."""


class Embedder:
    """The interface both providers implement."""

    name = "none"
    model = ""

    def available(self) -> bool:
        return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingsUnavailable("No embedding provider is configured.")

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


class OllamaEmbedder(Embedder):
    """A local Ollama daemon. Needs `ollama pull embeddinggemma` once."""

    name = "ollama"

    def __init__(self) -> None:
        self.base_url = settings.ollama_embedding_base_url.rstrip("/")
        self.model = settings.ollama_embedding_model

    def available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=4)
            return response.status_code < 400
        except requests.RequestException:
            return False

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=settings.rag_embedding_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise EmbeddingsUnavailable(
                f"Could not reach Ollama at {self.base_url}: {exc}. Start it with "
                "`ollama serve`, or set RAG_EMBEDDING_PROVIDER=none to use keyword search."
            ) from exc
        if response.status_code == 404:
            raise EmbeddingsUnavailable(
                f"Ollama has no model called {self.model!r}. Run `ollama pull {self.model}`."
            )
        if response.status_code >= 400:
            raise EmbeddingsUnavailable(
                f"Ollama returned HTTP {response.status_code}: {response.text[:200]}"
            )
        vectors = (response.json() or {}).get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingsUnavailable("Ollama returned a different number of vectors than texts.")
        return vectors


class GeminiEmbedder(Embedder):
    """Google's embedding endpoint, for when there is no local daemon."""

    name = "gemini"

    def __init__(self) -> None:
        self.model = settings.gemini_embedding_model

    def available(self) -> bool:
        return bool(settings.gemini_api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not settings.gemini_api_key:
            raise EmbeddingsUnavailable("GEMINI_API_KEY is not set.")
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.embed_content(
                model=self.model,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=settings.embedding_dimensions
                ),
            )
        except Exception as exc:  # noqa: BLE001 - any client failure is unavailability
            raise EmbeddingsUnavailable(f"Gemini embeddings failed: {exc}") from exc
        vectors = [list(item.values) for item in (response.embeddings or [])]
        if len(vectors) != len(texts):
            raise EmbeddingsUnavailable("Gemini returned a different number of vectors than texts.")
        return vectors


def get_embedder() -> Embedder:
    """The configured embedder. Never raises - check ``available()``."""
    choice = (settings.rag_embedding_provider or "ollama").strip().lower()
    if choice == "gemini":
        return GeminiEmbedder()
    if choice in ("none", "off", "keyword", "lexical"):
        return Embedder()
    return OllamaEmbedder()


def embed_in_batches(
    embedder: Embedder, texts: list[str], batch_size: int | None = None
) -> list[list[float]]:
    """Embed a long list without building one enormous request."""
    size = batch_size or settings.rag_embedding_batch_size
    vectors: list[list[float]] = []
    for start in range(0, len(texts), size):
        batch = texts[start:start + size]
        vectors.extend(embedder.embed(batch))
        log.info("[RAG] Embedded %d/%d chunk(s)", min(start + size, len(texts)), len(texts))
    return vectors


def describe() -> dict[str, Any]:
    """What the knowledge base would use right now, and whether it can."""
    embedder = get_embedder()
    return {
        "provider": embedder.name,
        "model": embedder.model,
        "available": embedder.available(),
        "base_url": getattr(embedder, "base_url", ""),
    }
