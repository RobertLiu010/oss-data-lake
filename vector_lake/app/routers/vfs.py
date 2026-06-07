"""VFS router — Virtual File System endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.vfs import (
    CacheInvalidateResponse,
    VfsGlobRequest,
    VfsGlobResponse,
    VfsGrepRequest,
    VfsGrepResponse,
    VfsLsRequest,
    VfsLsResponse,
    VfsReadResponse,
    VfsStatResponse,
)
from app.security import validate_id

router = APIRouter(
    prefix="/api/v1/workspaces/{ws}/collections/{col}/vfs",
    tags=["vfs"],
)


def _get_vfs_service(request: Request):
    return request.app.state.vfs_service


def _validate_vfs_path(path: str) -> str:
    """Validate that a VFS path does not contain path traversal sequences."""
    if '..' in path:
        raise ValueError(f"Path contains traversal sequence: {path}")
    return path


@router.post("/ls", response_model=VfsLsResponse)
async def vfs_ls(ws: str, col: str, req: VfsLsRequest, request: Request):
    """List entries under a virtual path."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        _validate_vfs_path(req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_vfs_service(request)
    entries = svc.ls(ws, col, req.path)
    return VfsLsResponse(path=req.path, entries=entries)


@router.get("/stat", response_model=VfsStatResponse)
async def vfs_stat(ws: str, col: str, path: str = "/", request: Request = None):
    """Get metadata for a virtual path."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        _validate_vfs_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_vfs_service(request)
    result = svc.stat(ws, col, path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    return result


@router.get("/read", response_model=VfsReadResponse)
async def vfs_read(ws: str, col: str, path: str, request: Request = None):
    """Read file content at virtual path."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        _validate_vfs_path(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        _validate_vfs_path(req.pattern)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_vfs_service(request)
    entries = svc.glob(ws, col, req.pattern)
    return VfsGlobResponse(pattern=req.pattern, entries=entries)


@router.post("/grep", response_model=VfsGrepResponse)
async def vfs_grep(ws: str, col: str, req: VfsGrepRequest, request: Request):
    """Grep over text files in VFS (regex pattern matching)."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
        if req.path:
            _validate_vfs_path(req.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
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


@router.post("/cache/invalidate", response_model=CacheInvalidateResponse)
async def vfs_cache_invalidate(ws: str, col: str, request: Request):
    """Invalidate the VFS cache for a specific workspace/collection."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_vfs_service(request)
    svc.invalidate_cache(ws, col)
    return CacheInvalidateResponse(status="ok", ws=ws, col=col)
