"""VFS models for request/response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VfsLsRequest(BaseModel):
    path: str = "/"  # virtual path, e.g. "/" or "/pricing.pdf"
    sort: str | None = None  # "name" | "size" | "modified"
    filter: str | None = None  # simple substring filter on name


class VfsEntry(BaseModel):
    """A single entry in VFS listing."""
    name: str
    path: str  # virtual path
    type: str  # "file" | "dir"
    size: int = 0
    entity_id: str | None = None
    rep_type: str | None = None
    entity_type: str | None = None
    status: str | None = None


class VfsLsResponse(BaseModel):
    path: str
    entries: list[VfsEntry] = Field(default_factory=list)


class VfsStatResponse(BaseModel):
    path: str
    type: str  # "file" | "dir"
    size: int = 0
    entity_id: str | None = None
    rep_type: str | None = None
    entity_type: str | None = None
    name: str | None = None
    status: str | None = None
    content_hash: str | None = None
    version: int | None = None
    labels: list[str] = Field(default_factory=list)


class VfsGlobRequest(BaseModel):
    pattern: str  # e.g. "**/*.md", "**/canonical_md"


class VfsGlobResponse(BaseModel):
    pattern: str
    entries: list[VfsEntry] = Field(default_factory=list)


class VfsGrepRequest(BaseModel):
    pattern: str  # regex pattern
    path: str = "/"  # virtual path prefix to scope the search
    max_results: int = 50
    context_lines: int = 2  # lines of context before/after match


class VfsGrepMatch(BaseModel):
    file_path: str  # virtual path
    line_number: int
    line_text: str
    context_before: list[str] = Field(default_factory=list)
    context_after: list[str] = Field(default_factory=list)
    entity_id: str | None = None
    rep_type: str | None = None
    entity_type: str | None = None
    name: str | None = None


class VfsGrepResponse(BaseModel):
    pattern: str
    matches: list[VfsGrepMatch] = Field(default_factory=list)
    total_matches: int = 0


class VfsReadResponse(BaseModel):
    path: str
    content: str
    size: int
    entity_id: str | None = None
    rep_type: str | None = None


class CacheInvalidateResponse(BaseModel):
    """Response model for cache invalidation."""
    status: str
    ws: str
    col: str
