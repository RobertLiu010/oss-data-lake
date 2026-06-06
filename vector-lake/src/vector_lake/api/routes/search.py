"""Search API routes (§14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["search"])


class SearchRequest(BaseModel):
    """Search request body."""

    query: str = Field(description="Search query")
    workspace_id: str = Field(description="Workspace ID")
    collection_id: str = Field(default="", description="Collection ID")
    top_k: int = Field(default=10, ge=1, le=100)
    search_type: str = Field(default="hybrid", description="semantic/lexical/hybrid/visual/audio")
    filters: dict[str, Any] | None = None
    include_snippets: bool = Field(default=True)
    include_provenance: bool = Field(default=True)


class SearchResult(BaseModel):
    """Single search result."""

    entity_id: str
    rep_type: str
    chunk_index: int
    text: str
    score: float
    snippet: str = ""
    provenance: dict[str, Any] | None = None


class SearchResponse(BaseModel):
    """Search response."""

    items: list[SearchResult]
    total: int
    query: str
    search_type: str


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest) -> SearchResponse:
    """Search the knowledge lake (§14.4)."""
    # TODO: delegate to VectorLakeService.search()
    return SearchResponse(items=[], total=0, query=req.query, search_type=req.search_type)


@router.get("/search")
async def search_get(
    query: str = Query(...),
    workspace_id: str = Query(...),
    collection_id: str = Query(default=""),
    top_k: int = Query(default=10),
    search_type: str = Query(default="hybrid"),
) -> SearchResponse:
    """Search via GET (convenience)."""
    req = SearchRequest(
        query=query,
        workspace_id=workspace_id,
        collection_id=collection_id,
        top_k=top_k,
        search_type=search_type,
    )
    return await search(req)
