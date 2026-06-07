"""Workspace and Collection management router."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path

router = APIRouter(prefix="/api/v1", tags=["workspaces"])

class WorkspaceCreate(BaseModel):
    workspace_id: str
    name: str = ""
    description: str = ""

class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    description: str
    collections_count: int = 0

class CollectionCreate(BaseModel):
    collection_id: str
    name: str = ""
    description: str = ""

class CollectionResponse(BaseModel):
    collection_id: str
    name: str
    description: str
    entity_count: int = 0

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
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / req.workspace_id
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
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / ws
    if not ws_dir.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
    cols_count = len([d for d in ws_dir.iterdir() if d.is_dir()])
    return WorkspaceResponse(workspace_id=ws, name=ws, description="", collections_count=cols_count)

@router.delete("/workspaces/{ws}")
async def delete_workspace(ws: str, request: Request):
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / ws
    if not ws_dir.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
    import shutil
    shutil.rmtree(ws_dir)
    return {"workspace_id": ws, "deleted": True}

# Collection endpoints
@router.get("/workspaces/{ws}/collections", response_model=list[CollectionResponse])
async def list_collections(ws: str, request: Request):
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    ws_dir = root / ws
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
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    col_dir = root / ws / req.collection_id
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
    settings = request.app.state.settings
    root = Path(settings.storage.local.root)
    col_dir = root / ws / col
    if not col_dir.exists():
        raise HTTPException(status_code=404, detail="Collection not found")
    import shutil
    shutil.rmtree(col_dir)
    return {"workspace_id": ws, "collection_id": col, "deleted": True}
