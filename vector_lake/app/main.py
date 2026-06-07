"""FastAPI application entry point for Vector Lake."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import load_settings
from app.storage.local import LocalStorage
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.event_bus import EventBus
from app.services.index import IndexService
from app.services.pipeline import PipelineService
from app.services.entity_service import EntityService
from app.services.vfs import VfsService
from app.services.reconciler import ReconcilerService
from app.services.watch import WatchService
from app.routers import entities, search, vfs, reconcile, events, workspaces


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = load_settings()

    storage = LocalStorage(settings)
    chunking = ChunkingService(settings)
    embedding = EmbeddingService(settings)
    index = IndexService(settings)
    event_bus = EventBus()
    pipeline = PipelineService(storage, chunking, embedding, index, settings, event_bus=event_bus)
    entity_service = EntityService(storage, pipeline, settings)
    vfs_service = VfsService(storage, settings)
    reconciler_service = ReconcilerService(storage, entity_service, pipeline, settings)
    watch_service = WatchService(storage, entity_service, settings)

    app.state.settings = settings
    app.state.entity_service = entity_service
    app.state.embedding_service = embedding
    app.state.index_service = index
    app.state.vfs_service = vfs_service
    app.state.reconciler_service = reconciler_service
    app.state.watch_service = watch_service
    app.state.event_bus = event_bus

    # Periodic cleanup of stale event bus subscribers
    async def _event_bus_cleanup_loop():
        while True:
            await asyncio.sleep(600)  # every 10 minutes
            event_bus.cleanup_stale_subscribers()

    cleanup_task = asyncio.create_task(_event_bus_cleanup_loop())

    yield

    # Shutdown: cancel cleanup task
    cleanup_task.cancel()
    # Shutdown: close embedding client
    await embedding.close()
    # Shutdown: stop all watch tasks
    await watch_service.shutdown()


app = FastAPI(
    title="Vector Lake",
    version="0.1.0",
    description="OSS-based knowledge lake with Entity → Representation → Chunk → Index model",
    lifespan=lifespan,
)

# Middleware (best practice: gzip large responses, allow CORS for web clients)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # v0.1: permissive; v0.2: restrict
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler (best practice: never leak internals)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = __import__("logging").getLogger(__name__)
    logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )

app.include_router(entities.router)
app.include_router(search.router)
app.include_router(vfs.router)
app.include_router(reconcile.router)
app.include_router(events.router)
app.include_router(workspaces.router)


@app.get("/health", tags=["system"])
async def health():
    """Liveness probe — returns 200 as long as the process is alive."""
    return {"status": "ok"}


@app.get("/readiness", tags=["system"])
async def readiness():
    """Readiness probe — returns 200 only when all critical services are ready."""
    settings = getattr(app.state, "settings", None)
    if settings is None:
        return JSONResponse(status_code=503, content={"ready": False, "reason": "not_initialized"})
    checks = {
        "storage": app.state.entity_service is not None,
        "pipeline": True,
        "vfs": app.state.vfs_service is not None,
    }
    if not all(checks.values()):
        return JSONResponse(status_code=503, content={"ready": False, "checks": checks})
    return {"ready": True, "checks": checks}
