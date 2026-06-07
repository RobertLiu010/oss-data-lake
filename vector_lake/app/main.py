"""FastAPI application entry point for Vector Lake."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import load_settings
from app.storage.local import LocalStorage
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.index import IndexService
from app.services.pipeline import PipelineService
from app.services.entity_service import EntityService
from app.services.vfs import VfsService
from app.services.reconciler import ReconcilerService
from app.services.watch import WatchService
from app.routers import entities, search, vfs, reconcile


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = load_settings()

    storage = LocalStorage(settings)
    chunking = ChunkingService(settings)
    embedding = EmbeddingService(settings)
    index = IndexService(settings)
    pipeline = PipelineService(storage, chunking, embedding, index, settings)
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

    yield

    # Shutdown: stop all watch tasks
    await watch_service.shutdown()


app = FastAPI(title="Vector Lake", version="0.1.0", lifespan=lifespan)

app.include_router(entities.router)
app.include_router(search.router)
app.include_router(vfs.router)
app.include_router(reconcile.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
