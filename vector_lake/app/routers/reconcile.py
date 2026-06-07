"""Reconciler and Watch Mode router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.reconcile import (
    DeadLetterResponse,
    ReconcileResponse,
    WatchStrategyCreate,
    WatchStrategyResponse,
)
from app.security import validate_id

router = APIRouter(prefix="/api/v1/workspaces/{ws}", tags=["reconcile-watch"])


def _get_reconciler(request: Request):
    return request.app.state.reconciler_service


def _get_watch_service(request: Request):
    return request.app.state.watch_service


# ---------------------------------------------------------------------------
# Reconciler endpoints
# ---------------------------------------------------------------------------

@router.post("/collections/{col}/reconcile", response_model=ReconcileResponse)
async def run_reconcile(ws: str, col: str, request: Request):
    """Run a full reconcile: detect drifts and auto-repair."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    reconciler = _get_reconciler(request)
    result = await reconciler.reconcile(ws, col)
    return ReconcileResponse(
        entities_scanned=result.entities_scanned,
        drift_count=result.drift_count,
        drifts_repaired=result.drifts_repaired,
        drifts=[
            {
                "entity_id": d.entity_id,
                "drift_type": d.drift_type.value,
                "detail": d.detail,
                "repaired": d.repaired,
                "repair_detail": d.repair_detail,
            }
            for d in result.drifts_found
        ],
        errors=result.errors,
    )


@router.get("/collections/{col}/reconcile/status")
async def reconcile_status(ws: str, col: str, request: Request):
    """Get the last reconcile result."""
    try:
        validate_id(ws, "ws")
        validate_id(col, "col")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    reconciler = _get_reconciler(request)
    result = reconciler.last_result

    # Check lock status
    lock_file = reconciler._lock_path(ws, col)
    lock_info = {"locked": False}
    if lock_file.exists():
        import time
        try:
            mtime = lock_file.stat().st_mtime
            age = time.time() - mtime
            lock_info = {
                "locked": True,
                "lock_age_seconds": round(age, 1),
            }
        except FileNotFoundError:
            lock_info = {"locked": False}

    if result is None:
        return {"status": "never_run", "lock": lock_info}
    return {
        "status": "completed",
        "entities_scanned": result.entities_scanned,
        "drift_count": result.drift_count,
        "drifts_repaired": result.drifts_repaired,
        "started_at": str(result.started_at),
        "finished_at": str(result.finished_at),
        "lock": lock_info,
    }


# ---------------------------------------------------------------------------
# Watch Mode endpoints
# ---------------------------------------------------------------------------

@router.get("/watch-strategies", response_model=list[WatchStrategyResponse])
async def list_watch_strategies(ws: str, request: Request):
    """List all watch strategies for a workspace."""
    try:
        validate_id(ws, "ws")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_watch_service(request)
    results = []
    for wid, strategy in svc.watches.items():
        results.append(WatchStrategyResponse(
            watch_id=strategy.watch_id,
            workspace_id=strategy.workspace_id,
            collection_id=strategy.collection_id,
            watch_dir=strategy.watch_dir,
            allowed_extensions=strategy.allowed_extensions,
            entity_id_strategy=strategy.entity_id_strategy,
            on_conflict=strategy.on_conflict,
            recursive=strategy.recursive,
            max_file_size_mb=strategy.max_file_size_mb,
            backend=strategy.backend,
            scan_interval=strategy.scan_interval,
            status=strategy.status.value,
            total_events=strategy.total_events,
            total_processed=strategy.total_processed,
            total_errors=strategy.total_errors,
            last_scan_at=str(strategy.last_scan_at) if strategy.last_scan_at else None,
        ))
    return results


@router.post("/watch-strategies", status_code=201, response_model=WatchStrategyResponse)
async def create_watch_strategy(ws: str, req: WatchStrategyCreate, request: Request):
    """Create a new watch strategy."""
    try:
        validate_id(ws, "ws")
        validate_id(req.collection_id, "collection_id")
        if '..' in req.watch_dir:
            raise ValueError("watch_dir contains path traversal sequence")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    from app.services.watch import WatchStrategy

    svc = _get_watch_service(request)
    watch_id = f"watch_{len(svc.watches) + 1:03d}"

    strategy = WatchStrategy(
        watch_id=watch_id,
        workspace_id=ws,
        collection_id=req.collection_id,
        watch_dir=req.watch_dir,
        allowed_extensions=req.allowed_extensions,
        entity_id_strategy=req.entity_id_strategy,
        on_conflict=req.on_conflict,
        recursive=req.recursive,
        max_file_size_mb=req.max_file_size_mb,
        backend=req.backend,
        scan_interval=req.scan_interval,
    )

    try:
        svc.create_watch(strategy)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return WatchStrategyResponse(
        watch_id=strategy.watch_id,
        workspace_id=strategy.workspace_id,
        collection_id=strategy.collection_id,
        watch_dir=strategy.watch_dir,
        allowed_extensions=strategy.allowed_extensions,
        entity_id_strategy=strategy.entity_id_strategy,
        on_conflict=strategy.on_conflict,
        recursive=strategy.recursive,
        max_file_size_mb=strategy.max_file_size_mb,
        backend=strategy.backend,
        scan_interval=strategy.scan_interval,
        status=strategy.status.value,
    )


@router.post("/watch-strategies/{watch_id}/start")
async def start_watch(ws: str, watch_id: str, request: Request):
    """Start watching (begin background polling)."""
    try:
        validate_id(ws, "ws")
        validate_id(watch_id, "watch_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_watch_service(request)
    try:
        svc.start_watch(watch_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"watch_id": watch_id, "status": "active"}


@router.post("/watch-strategies/{watch_id}/pause")
async def pause_watch(ws: str, watch_id: str, request: Request):
    """Pause a watch strategy."""
    try:
        validate_id(ws, "ws")
        validate_id(watch_id, "watch_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_watch_service(request)
    try:
        svc.pause_watch(watch_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"watch_id": watch_id, "status": "paused"}


@router.delete("/watch-strategies/{watch_id}")
async def delete_watch(ws: str, watch_id: str, request: Request):
    """Stop and delete a watch strategy."""
    try:
        validate_id(ws, "ws")
        validate_id(watch_id, "watch_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_watch_service(request)
    try:
        svc.stop_watch(watch_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"watch_id": watch_id, "status": "deleted"}


# ---------------------------------------------------------------------------
# Dead Letter endpoints
# ---------------------------------------------------------------------------

@router.get("/dead-letters", response_model=list[DeadLetterResponse])
async def list_dead_letters(ws: str, request: Request):
    """List all dead letter entries."""
    try:
        validate_id(ws, "ws")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_watch_service(request)
    return [
        DeadLetterResponse(
            entry_id=dl.entry_id,
            workspace_id=dl.workspace_id,
            collection_id=dl.collection_id,
            file_path=dl.file_path,
            error=dl.error,
            created_at=str(dl.created_at),
            replayed=dl.replayed,
        )
        for dl in svc.dead_letters
        if dl.workspace_id == ws
    ]


@router.post("/dead-letters/{entry_id}/replay")
async def replay_dead_letter(ws: str, entry_id: str, request: Request):
    """Replay a dead letter entry."""
    try:
        validate_id(ws, "ws")
        validate_id(entry_id, "entry_id")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_watch_service(request)
    result = await svc.replay_dead_letter(entry_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Dead letter entry not found")
    return {"entry_id": entry_id, "result": result}


@router.post("/dead-letters/cleanup")
async def cleanup_dead_letters(ws: str, request: Request):
    """Clean up old dead letter entries."""
    try:
        validate_id(ws, "ws")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    svc = _get_watch_service(request)
    removed = svc.cleanup_dead_letters()
    return {"removed": removed}
