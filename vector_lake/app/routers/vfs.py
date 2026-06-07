"""VFS router — Virtual File System endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.vfs import (
    VfsGlobRequest,
    VfsGlobResponse,
    VfsGrepRequest,
    VfsGrepResponse,
    VfsLsRequest,
    VfsLsResponse,
    VfsReadResponse,
    VfsStatResponse,
)

router = APIRouter(
    prefix="/api/v1/workspaces/{ws}/collections/{col}/vfs",
    tags=["vfs"],
)


def _get_vfs_service(request: Request):
    return request.app.state.vfs_service


@router.post("/ls", response_model=VfsLsResponse)
async def vfs_ls(ws: str, col: str, req: VfsLsRequest, request: Request):
    """List entries under a virtual path."""
    svc = _get_vfs_service(request)
    entries = svc.ls(ws, col, req.path)
    return VfsLsResponse(path=req.path, entries=entries)


@router.get("/stat", response_model=VfsStatResponse)
async def vfs_stat(ws: str, col: str, path: str = "/", request: Request = None):
    """Get metadata for a virtual path."""
    svc = _get_vfs_service(request)
    result = svc.stat(ws, col, path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    return result


@router.get("/read", response_model=VfsReadResponse)
async def vfs_read(ws: str, col: str, path: str, request: Request = None):
    """Read file content at virtual path."""
    svc = _get_vfs_service(request)
    result = svc.read(ws, col, path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    content, entity_id, rep_type = result
    return VfsReadResponse(
        path=path,
        content=content,
        size=len(content),
        entity_id=entity_id,
        rep_type=rep_type,
    )


@router.post("/glob", response_model=VfsGlobResponse)
async def vfs_glob(ws: str, col: str, req: VfsGlobRequest, request: Request):
    """Glob match over virtual paths (e.g. **/*.md, **/canonical.md)."""
    svc = _get_vfs_service(request)
    entries = svc.glob(ws, col, req.pattern)
    return VfsGlobResponse(pattern=req.pattern, entries=entries)


@router.post("/grep", response_model=VfsGrepResponse)
async def vfs_grep(ws: str, col: str, req: VfsGrepRequest, request: Request):
    """Grep over text files in VFS (regex pattern matching)."""
    svc = _get_vfs_service(request)
    matches = svc.grep(
        ws, col, req.pattern,
        path_prefix=req.path,
        max_results=req.max_results,
        context_lines=req.context_lines,
    )
    return VfsGrepResponse(
        pattern=req.pattern,
        matches=matches,
        total_matches=len(matches),
    )
