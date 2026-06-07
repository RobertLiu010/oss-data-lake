"""Entity CRUD + file upload router."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from app.models.entity import Entity, EntityPatchRequest, PipelineStatus
from app.security import validate_id

router = APIRouter(
    prefix="/api/v1/workspaces/{ws}/collections/{col}/entities",
    tags=["entities"],
)


def _get_entity_service(request: Request):
    return request.app.state.entity_service


@router.post("", status_code=201, response_model=Entity)
async def create_entity(
    ws: str,
    col: str,
    file: UploadFile = File(...),
    request: Request = None,
):
    """Upload a file and create an entity. Only .md supported in v0.1 MVP."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_entity_service(request)
    try:
        entity = await svc.create_from_file(ws, col, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {exc}")
    return entity


@router.get("", response_model=list[Entity])
async def list_entities(
    ws: str,
    col: str,
    status: str = Query(None, description="Filter by status: enabled/hidden/deleted"),
    request: Request = None,
):
    """List all entities, optionally filtered by status."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_entity_service(request)
    entities = await svc.list_entities(ws, col, status_filter=status)
    return entities


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(ws: str, col: str, entity_id: str, request: Request):
    """Get entity details."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        validate_id(entity_id, "entity_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_entity_service(request)
    entity = await svc.get_entity(ws, col, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/{entity_id}/status", response_model=PipelineStatus)
async def get_entity_status(ws: str, col: str, entity_id: str, request: Request):
    """Get entity pipeline processing status — reps, chunks, index."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        validate_id(entity_id, "entity_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_entity_service(request)
    status = await svc.get_pipeline_status(ws, col, entity_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return status


@router.patch("/{entity_id}", response_model=Entity)
async def patch_entity(
    ws: str,
    col: str,
    entity_id: str,
    req: EntityPatchRequest,
    request: Request,
):
    """Update entity status (enabled/hidden/deleted) and/or labels."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        validate_id(entity_id, "entity_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_entity_service(request)
    entity = await svc.patch_entity(
        ws, col, entity_id,
        status=req.status,
        labels=req.labels,
    )
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.put("/{entity_id}/content", response_model=Entity)
async def update_entity_content(
    ws: str,
    col: str,
    entity_id: str,
    file: UploadFile = File(...),
    request: Request = None,
):
    """Re-upload entity content. Triggers cascade rebuild:
    source_original → stale downstream reps → pipeline re-execute → index re-sync.
    """
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        validate_id(entity_id, "entity_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_entity_service(request)
    content = await file.read()
    entity = await svc.update_entity_content(ws, col, entity_id, content)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.delete("/{entity_id}")
async def delete_entity(
    ws: str,
    col: str,
    entity_id: str,
    hard: bool = Query(False, description="Hard delete: remove storage + index"),
    request: Request = None,
):
    """Delete an entity. Soft delete by default (status=deleted), hard delete with ?hard=true."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        validate_id(entity_id, "entity_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_entity_service(request)
    success = await svc.delete_entity(ws, col, entity_id, hard=hard)
    if not success:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {
        "entity_id": entity_id,
        "deleted": True,
        "hard": hard,
    }
