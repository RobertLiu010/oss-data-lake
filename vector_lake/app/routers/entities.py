"""Entity CRUD + file upload router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, File, Request

from app.models.entity import Entity

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
    svc = _get_entity_service(request)
    try:
        entity = await svc.create_from_file(ws, col, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create entity: {exc}")
    return entity


@router.get("", response_model=list[Entity])
async def list_entities(ws: str, col: str, request: Request):
    """List all entities."""
    svc = _get_entity_service(request)
    entities = await svc.list_entities(ws, col)
    return entities


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(ws: str, col: str, entity_id: str, request: Request):
    """Get entity details."""
    svc = _get_entity_service(request)
    entity = await svc.get_entity(ws, col, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity
