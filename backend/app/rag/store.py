"""Where the crawled knowledge lives on disk.

Three files, all in ``data/rag``::

    chunks.jsonl   one passage per line, human-readable
    vectors.f32    their embeddings, raw float32, pre-normalised
    index.json     how many, what shape, and which sites

The vectors are written with the standard library, so a completed embedding run
is **never** thrown away for want of an optional package. numpy, when present,
only makes searching them faster - it is not needed to keep them.

That distinction is the whole point of this file: an earlier version stored the
matrix with ``numpy.save`` and silently dropped it when numpy was missing, so a
long, successful embedding run ended with "keyword search only".

Re-ingesting a site replaces that site's chunks - including its subdomains -
and leaves other sites alone.
"""
from __future__ import annotations

import json
import logging
import math
import time
from array import array
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import settings

log = logging.getLogger("campusai.rag")

try:  # optional: speed, not capability
    import numpy as _np
except ImportError:  # pragma: no cover - exercised only where numpy is absent
    _np = None


class Vectors:
    """The embedding matrix, however it can be held in this environment.

    ``matrix`` is a numpy array when numpy is installed and None otherwise;
    ``row(i)`` always works. Rows are unit-normalised at save time, so a
    similarity is a plain dot product either way.
    """

    def __init__(self, flat: array, dim: int, count: int) -> None:
        self.flat = flat
        self.dim = dim
        self.count = count
        self.matrix = None
        if _np is not None and count and dim:
            self.matrix = _np.frombuffer(
                memoryview(flat), dtype=_np.float32, count=count * dim
            ).reshape(count, dim)

    def __len__(self) -> int:
        return self.count

    def row(self, index: int) -> memoryview:
        start = index * self.dim
        return memoryview(self.flat)[start:start + self.dim]

    @property
    def fast(self) -> bool:
        return self.matrix is not None


def store_dir() -> Path:
    path = Path(settings.rag_store_dir)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path


def _chunks_path() -> Path:
    return store_dir() / "chunks.jsonl"


def _vectors_path() -> Path:
    return store_dir() / "vectors.f32"


def _meta_path() -> Path:
    return store_dir() / "index.json"


def _legacy_vectors_path() -> Path:
    """The numpy-only file written by the previous version."""
    return store_dir() / "vectors.npy"


def host_of(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, site_host: str) -> bool:
    """True for the site and anything under it, so a re-crawl replaces both.

    The crawler follows subdomains (admission.lpu.in, happenings.lpu.in), so a
    replace that only matched the bare host would leave the old subdomain
    chunks behind and add fresh copies beside them.
    """
    host = host_of(url)
    return bool(host) and (host == site_host or host.endswith("." + site_host))


def _read_meta() -> dict[str, Any]:
    path = _meta_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load() -> tuple[list[dict[str, Any]], Vectors | None]:
    """Every chunk, and the vectors if any were stored."""
    path = _chunks_path()
    if not path.exists():
        return [], None

    chunks: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # one damaged line must not lose the whole store

    vectors = _load_vectors(len(chunks))
    return chunks, vectors


def _load_vectors(expected: int) -> Vectors | None:
    meta = _read_meta()
    dim = int(meta.get("dimensions") or 0)
    path = _vectors_path()

    if path.exists() and dim:
        flat = array("f")
        with path.open("rb") as handle:
            data = handle.read()
        flat.frombytes(data)
        count = len(flat) // dim
        if count != expected:
            log.warning(
                "[RAG] %d vector(s) for %d chunk(s): ignoring them and searching by "
                "keyword until the next ingest.", count, expected,
            )
            return None
        return Vectors(flat, dim, count)

    legacy = _legacy_vectors_path()
    if legacy.exists() and _np is not None:
        # Written by an older build; read it once so nobody has to re-embed.
        try:
            matrix = _np.load(legacy).astype("float32")
            if len(matrix) == expected:
                flat = array("f")
                flat.frombytes(matrix.tobytes())
                log.info("[RAG] Converted the previous vectors.npy store.")
                return Vectors(flat, matrix.shape[1], len(matrix))
        except Exception as exc:  # noqa: BLE001
            log.warning("[RAG] Could not read %s: %s", legacy, exc)
    return None


def _normalise(vectors: list[list[float]]) -> tuple[array, int]:
    """Flatten to unit-length rows, so a later search is a dot product."""
    dim = len(vectors[0])
    flat = array("f")
    for vector in vectors:
        if len(vector) != dim:
            raise ValueError(
                f"Embeddings have inconsistent sizes ({len(vector)} vs {dim}); "
                "the store needs one shape."
            )
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        flat.extend(value / norm for value in vector)
    return flat, dim


def save(chunks: list[dict[str, Any]], vectors: list[list[float]] | None) -> dict[str, Any]:
    """Write the store atomically: a half-written index is worse than none."""
    directory = store_dir()
    directory.mkdir(parents=True, exist_ok=True)

    temp = _chunks_path().with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    temp.replace(_chunks_path())

    dimensions = 0
    if vectors and len(vectors) == len(chunks):
        flat, dimensions = _normalise(vectors)
        temp_vectors = _vectors_path().with_suffix(".tmp")
        temp_vectors.write_bytes(flat.tobytes())
        temp_vectors.replace(_vectors_path())
    else:
        # No usable vectors this time: remove stale ones rather than leave them
        # pointing at chunks that no longer exist.
        for path in (_vectors_path(), _legacy_vectors_path()):
            if path.exists():
                path.unlink()

    meta = {
        "chunks": len(chunks),
        "dimensions": dimensions,
        "vectors": bool(dimensions),
        "sites": sorted({host_of(chunk.get("url", "")) for chunk in chunks if chunk.get("url")}),
        "updated_at": time.time(),
    }
    _meta_path().write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def replace_site(
    site_host: str, new_chunks: list[dict[str, Any]], new_vectors: list[list[float]] | None
) -> dict[str, Any]:
    """Swap in a fresh crawl of one site, leaving other sites untouched."""
    existing, existing_vectors = load()
    keep = [
        index for index, chunk in enumerate(existing)
        if not same_site(chunk.get("url", ""), site_host)
    ]
    kept = [existing[index] for index in keep]

    kept_vectors: list[list[float]] | None = None
    if existing_vectors is not None:
        kept_vectors = [list(existing_vectors.row(index)) for index in keep]

    if new_vectors and kept and kept_vectors is None:
        # Some chunks would have vectors and some would not; a partial matrix
        # cannot be searched, so say so and keep the new ones only.
        log.info("[RAG] Previously stored chunks have no vectors; dropping them so the "
                 "new ones can be searched by meaning.")
        kept, kept_vectors = [], []

    combined = kept + new_chunks
    combined_vectors = ((kept_vectors or []) + list(new_vectors)) if new_vectors else None
    return save(combined, combined_vectors)


def stats() -> dict[str, Any]:
    """What is in the knowledge base right now."""
    meta = _read_meta()
    chunks, vectors = load()
    pages = len({chunk.get("url") for chunk in chunks if chunk.get("url")})
    return {
        "chunks": len(chunks),
        "pages": pages,
        "sites": meta.get("sites") or sorted(
            {host_of(c.get("url", "")) for c in chunks if c.get("url")}
        ),
        "has_vectors": vectors is not None,
        "dimensions": vectors.dim if vectors else 0,
        "fast_search": bool(vectors and vectors.fast),
        "numpy_available": _np is not None,
        "updated_at": meta.get("updated_at"),
        "location": str(store_dir()),
    }


def clear() -> dict[str, Any]:
    for path in (_chunks_path(), _vectors_path(), _legacy_vectors_path(), _meta_path()):
        if path.exists():
            path.unlink()
    return {"cleared": True, "location": str(store_dir())}
