"""Entity API routes (§14)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from vector_lake.models.entity import Entity

router = APIRouter(prefix="/v1", tags=["entities"])


@router.post("/entities", status_code=201)
async def create_entity(
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
    entity_id: str = Query(...),
    source_path: str = Query(...),
    labels: dict[str, str] | None = None,
) -> Entity:
    """Create a new Entity (§14.1).

    Triggers RepPipeline dispatch via Redis Streams.
    """
    # TODO: delegate to EntityService
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
) -> Entity:
    """Get entity details (§14.2)."""
    # TODO: delegate to VFS.get_entity()
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/entities")
async def list_entities(
    workspace_id: str = Query(...),
    collection_id: str = Query(default=""),
    entity_type: str = Query(default=""),
    labels: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=1000),
    cursor: str = Query(default=""),
) -> dict[str, Any]:
    """List entities (§14.3)."""
    # TODO: delegate to VFS.ls() + tag scanning
    return {"items": [], "next_cursor": "", "total": 0}


@router.delete("/entities/{entity_id}")
async def delete_entity(
    entity_id: str,
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
) -> dict[str, str]:
    """Soft delete entity (§5.10.3). Keeps Lance data for 30 days."""
    # TODO: update rag_status=deleted in Entity Tag
    return {"status": "deleted", "entity_id": entity_id}


@router.post("/entities/{entity_id}/destroy")
async def destroy_entity(
    entity_id: str,
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
) -> dict[str, str]:
    """Physically delete entity and all data."""
    # TODO: delete all OSS objects + Lance data
    return {"status": "destroyed", "entity_id": entity_id}


@router.post("/entities/{entity_id}/rebuild")
async def rebuild_entity(
    entity_id: str,
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
    pipeline_id: str = Query(default=""),
) -> dict[str, Any]:
    """Trigger pipeline rebuild for an entity."""
    # TODO: dispatch RepPipeline rebuild
    return {"status": "dispatched", "entity_id": entity_id, "pipeline_id": pipeline_id}


@router.get("/entities/{entity_id}/status")
async def entity_status(
    entity_id: str,
    workspace_id: str = Query(...),
    collection_id: str = Query(...),
) -> dict[str, Any]:
    """Get entity pipeline status (rep_status + index_status)."""
    # TODO: read from VFS
    return {
        "entity_id": entity_id,
        "rep_status": {},
        "index_status": {},
    }
