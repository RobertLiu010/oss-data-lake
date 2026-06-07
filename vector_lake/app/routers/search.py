"""Search endpoint router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.search import SearchRequest, SearchResult, SearchType
from app.security import validate_id

router = APIRouter(
    prefix="/api/v1/workspaces/{ws}/collections/{col}",
    tags=["search"],
)


@router.post("/search", response_model=list[SearchResult])
async def search(ws: str, col: str, req: SearchRequest, request: Request):
    """Search: semantic, lexical, or hybrid (RRF) based on search_type."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    embedding_svc = request.app.state.embedding_service
    index_svc = request.app.state.index_service

    # Lexical-only search does not need embeddings
    if req.search_type == SearchType.LEXICAL:
        try:
            results = await index_svc.search_lexical(
                ws, col, req.query, top_k=req.top_k,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Index search error: {exc}",
            )
        return results

    # Semantic and hybrid both need a query vector
    try:
        query_vector = await embedding_svc.embed_query(req.query)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Embedding service error: {exc}",
        )

    if req.search_type == SearchType.HYBRID:
        try:
            results = await index_svc.search_hybrid(
                ws, col, req.query, query_vector,
                top_k=req.top_k,
                rrf_k=req.rrf_k,
                semantic_weight=req.semantic_weight,
                lexical_weight=req.lexical_weight,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Index search error: {exc}",
            )
        return results

    # Default: semantic search
    try:
        results = await index_svc.search(ws, col, query_vector, top_k=req.top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Index search error: {exc}",
        )
    return results
