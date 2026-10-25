from typing import Any

from pydantic import BaseModel, Field


class RAGIngestRequest(BaseModel):
    #: Defaults to COLLEGE_WEBSITE_URL when omitted.
    url: str | None = Field(default=None, max_length=1000)
    max_pages: int | None = Field(default=None, ge=1, le=2000)
    max_depth: int | None = Field(default=None, ge=0, le=6)


class RAGIngestResponse(BaseModel):
    source_url: str
    pages: int
    chunks: int
    #: False when no embedder was reachable - the pages are still searchable
    #: by keyword, and this says so rather than pretending otherwise.
    embedded: bool = False
    embedding_provider: str = ""
    embedding_model: str = ""
    note: str = ""
    seconds: float = 0.0
    store: dict[str, Any] = {}
    sample_pages: list[dict[str, Any]] = []


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=20)
