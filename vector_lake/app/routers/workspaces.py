"""Workspace and Collection management router."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.models.workspace import CollectionCreate, CollectionResponse, WorkspaceCreate, WorkspaceResponse
from app.security import validate_id, validate_path_under_root

router = APIRouter(prefix="/api/v1", tags=["workspaces"])

# Workspace endpoints
@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces(request: Request):
    """List all workspaces."""
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    if not root.exists():
        return []
    results = []
    for ws_dir in sorted(root.iterdir()):
        if ws_dir.is_dir():
            cols_count = len([d for d in ws_dir.iterdir() if d.is_dir()])
            results.append(WorkspaceResponse(
                workspace_id=ws_dir.name,
                name=ws_dir.name,
                description="",
                collections_count=cols_count,
            ))
    return results

@router.post("/workspaces", status_code=201, response_model=WorkspaceResponse)
async def create_workspace(req: WorkspaceCreate, request: Request):
    """Create a new workspace."""
    try:
        validate_id(req.workspace_id, "workspace_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / req.workspace_id
    validate_path_under_root(ws_dir, root)
    if ws_dir.exists():
        raise HTTPException(status_code=409, detail=f"Workspace {req.workspace_id} already exists")
    ws_dir.mkdir(parents=True, exist_ok=True)
    return WorkspaceResponse(
        workspace_id=req.workspace_id,
        name=req.name or req.workspace_id,
        description=req.description,
    )

@router.get("/workspaces/{ws}", response_model=WorkspaceResponse)
async def get_workspace(ws: str, request: Request):
    try:
        validate_id(ws, "ws")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / ws
    validate_path_under_root(ws_dir, root)
    if not ws_dir.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
    cols_count = len([d for d in ws_dir.iterdir() if d.is_dir()])
    return WorkspaceResponse(workspace_id=ws, name=ws, description="", collections_count=cols_count)

@router.delete("/workspaces/{ws}")
async def delete_workspace(ws: str, request: Request):
    try:
        validate_id(ws, "ws")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / ws
    validate_path_under_root(ws_dir, root)
    if not ws_dir.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Check for active watch strategies referencing this workspace
    watch_service = request.app.state.watch_service
    active_watches = [
        s for s in watch_service.watches.values()
        if s.workspace_id == ws
    ]
    if active_watches:
        watch_ids = [s.watch_id for s in active_watches]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete workspace: active watch strategies reference it: {watch_ids}",
        )

    # Collect collection names before removing directory
    col_names = [d.name for d in ws_dir.iterdir() if d.is_dir()]

    import shutil
    shutil.rmtree(ws_dir)

    # Clean up LanceDB index tables for all collections in this workspace
    try:
        index_svc = request.app.state.index_service
        for col_name in col_names:
            index_svc.drop_table(ws, col_name)
    except Exception:
        pass  # best-effort: index cleanup failure should not block deletion

    return {"workspace_id": ws, "deleted": True}

# Collection endpoints
@router.get("/workspaces/{ws}/collections", response_model=list[CollectionResponse])
async def list_collections(ws: str, request: Request):
    try:
        validate_id(ws, "ws")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / ws
    validate_path_under_root(ws_dir, root)
    if not ws_dir.exists():
        return []
    results = []
    for col_dir in sorted(ws_dir.iterdir()):
        if col_dir.is_dir():
            entity_count = len([d for d in col_dir.iterdir() if d.is_dir()])
            results.append(CollectionResponse(
                collection_id=col_dir.name,
                name=col_dir.name,
                description="",
                entity_count=entity_count,
            ))
    return results

@router.post("/workspaces/{ws}/collections", status_code=201, response_model=CollectionResponse)
async def create_collection(ws: str, req: CollectionCreate, request: Request):
    try:
        validate_id(ws, "ws")
        validate_id(req.collection_id, "collection_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    col_dir = root / ws / req.collection_id
    validate_path_under_root(col_dir, root)
    if col_dir.exists():
        raise HTTPException(status_code=409, detail=f"Collection {req.collection_id} already exists")
    col_dir.mkdir(parents=True, exist_ok=True)
    return CollectionResponse(
        collection_id=req.collection_id,
        name=req.name or req.collection_id,
        description=req.description,
    )

@router.delete("/workspaces/{ws}/collections/{col}")
async def delete_collection(ws: str, col: str, request: Request):
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    col_dir = root / ws / col
    validate_path_under_root(col_dir, root)
    if not col_dir.exists():
        raise HTTPException(status_code=404, detail="Collection not found")

    # Check for active watch strategies referencing this collection
    watch_service = request.app.state.watch_service
    active_watches = [
        s for s in watch_service.watches.values()
        if s.workspace_id == ws and s.collection_id == col
    ]
    if active_watches:
        watch_ids = [s.watch_id for s in active_watches]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete collection: active watch strategies reference it: {watch_ids}",
        )

    import shutil
    shutil.rmtree(col_dir)

    # Clean up LanceDB index table for this collection
    try:
        index_svc = request.app.state.index_service
        index_svc.drop_table(ws, col)
    except Exception:
        pass  # best-effort

    return {"workspace_id": ws, "collection_id": col, "deleted": True}
