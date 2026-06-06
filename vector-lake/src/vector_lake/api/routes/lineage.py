"""Lineage API routes (§14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1", tags=["lineage"])


@router.get("/lineage/{entity_id}")
async def get_lineage(
    entity_id: str,
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
) -> dict[str, Any]:
    """Get entity lineage (§2.5). Derived from directory hierarchy + Pipeline registry."""
    # TODO: delegate to LineageService
    return {"entity_id": entity_id, "edges": [], "depth": 0}


@router.get("/lineage/{entity_id}/impact")
async def impact_analysis(
    entity_id: str,
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
    rep_type: str = Query(default=""),
) -> dict[str, Any]:
    """Impact analysis: what downstream Reps/Indexes are affected by changes."""
    # TODO: delegate to LineageService
    return {"entity_id": entity_id, "affected_reps": [], "affected_indexes": []}
