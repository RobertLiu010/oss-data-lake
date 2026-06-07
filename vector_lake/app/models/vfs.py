"""VFS models for request/response."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class VfsLsRequest(BaseModel):
    path: str = "/"  # virtual path, e.g. "/" or "/pricing.pdf"
    sort: Optional[str] = None  # "name" | "size" | "modified"
    filter: Optional[str] = None  # simple substring filter on name


class VfsEntry(BaseModel):
    """A single entry in VFS listing."""
    name: str
    path: str  # virtual path
    type: str  # "file" | "dir"
    size: int = 0
    entity_id: Optional[str] = None
    rep_type: Optional[str] = None
    entity_type: Optional[str] = None
    status: Optional[str] = None


class VfsLsResponse(BaseModel):
    path: str
    entries: list[VfsEntry] = Field(default_factory=list)


class VfsStatResponse(BaseModel):
    path: str
    type: str  # "file" | "dir"
    size: int = 0
    entity_id: Optional[str] = None
    rep_type: Optional[str] = None
    entity_type: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    content_hash: Optional[str] = None
    version: Optional[int] = None
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
    entity_id: Optional[str] = None
    rep_type: Optional[str] = None
    entity_type: Optional[str] = None
    name: Optional[str] = None


class VfsGrepResponse(BaseModel):
    pattern: str
    matches: list[VfsGrepMatch] = Field(default_factory=list)
    total_matches: int = 0


class VfsReadResponse(BaseModel):
    path: str
    content: str
    size: int
    entity_id: Optional[str] = None
    rep_type: Optional[str] = None
