"""Search endpoint router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.search import SearchRequest, SearchResult

router = APIRouter(
    prefix="/api/v1/workspaces/{ws}/collections/{col}",
    tags=["search"],
)


@router.post("/search", response_model=list[SearchResult])
async def search(ws: str, col: str, req: SearchRequest, request: Request):
    """Semantic search: embed query → search LanceDB → return results."""
    embedding_svc = request.app.state.embedding_service
    index_svc = request.app.state.index_service

    try:
        query_vector = await embedding_svc.embed_query(req.query)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Embedding service error: {exc}",
        )

    try:
        results = await index_svc.search(ws, col, query_vector, top_k=req.top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Index search error: {exc}",
        )

    return results
