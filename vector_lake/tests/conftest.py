"""Shared test fixtures for Vector-Lake test suite."""

from __future__ import annotations

import os

# MUST set EMBEDDING_MOCK before importing any app modules
os.environ["EMBEDDING_MOCK"] = "1"

from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.entity_service import EntityService
from app.services.event_bus import EventBus
from app.services.index import IndexService
from app.services.pipeline import PipelineService
from app.services.reconciler import ReconcilerService
from app.services.templates import register_builtin_templates
from app.services.vfs import VfsService
from app.services.watch import WatchService
from app.storage.local import LocalStorage

# ---------------------------------------------------------------------------
# Session-scoped setup: register builtin templates once
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _register_builtin_templates():
    """Ensure builtin templates are in the global registry for all tests."""
    register_builtin_templates()

# ---------------------------------------------------------------------------
# Synchronous fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def tmp_lance_dir(tmp_path: Path) -> Path:
    """Create a temporary LanceDB data directory."""
    lance_dir = tmp_path / "lance_data"
    lance_dir.mkdir()
    return lance_dir


@pytest.fixture
def settings(tmp_data_dir: Path, tmp_lance_dir: Path) -> Settings:
    """Settings pointing to temp directories with EMBEDDING_MOCK=1."""
    return Settings(
        storage={"backend": "local", "local": {"root": str(tmp_data_dir)}},
        lance={"data_dir": str(tmp_lance_dir)},
        embedding={"base_url": "http://127.0.0.1:8006", "model": "embedding-v5"},
        vfs={"cache_ttl": 0.0},  # disable cache for tests by default
    )


@pytest.fixture
def storage(settings: Settings) -> LocalStorage:
    """LocalStorage instance backed by a temp directory."""
    return LocalStorage(settings)


@pytest.fixture
def chunking_service(settings: Settings) -> ChunkingService:
    """ChunkingService with default settings."""
    return ChunkingService(settings)


@pytest.fixture
def embedding_service(settings: Settings) -> EmbeddingService:
    """EmbeddingService in mock mode."""
    return EmbeddingService(settings)


@pytest.fixture
def event_bus() -> EventBus:
    """Fresh EventBus instance."""
    return EventBus()


@pytest.fixture
def index_service(settings: Settings) -> IndexService:
    """IndexService with temp LanceDB directory."""
    return IndexService(settings)


@pytest.fixture
def pipeline_service(
    storage: LocalStorage,
    chunking_service: ChunkingService,
    embedding_service: EmbeddingService,
    index_service: IndexService,
    settings: Settings,
    event_bus: EventBus,
) -> PipelineService:
    """PipelineService with all dependencies."""
    return PipelineService(
        storage=storage,
        chunking=chunking_service,
        embedding=embedding_service,
        index=index_service,
        settings=settings,
        event_bus=event_bus,
    )


@pytest.fixture
def entity_service(
    storage: LocalStorage,
    pipeline_service: PipelineService,
    settings: Settings,
) -> EntityService:
    """EntityService with all dependencies."""
    return EntityService(
        storage=storage,
        pipeline=pipeline_service,
        settings=settings,
    )


@pytest.fixture
def vfs_service(storage: LocalStorage, settings: Settings) -> VfsService:
    """VfsService with temp storage and cache disabled."""
    return VfsService(storage, settings)


@pytest.fixture
def reconciler_service(
    storage: LocalStorage,
    entity_service: EntityService,
    pipeline_service: PipelineService,
    settings: Settings,
) -> ReconcilerService:
    """ReconcilerService with all dependencies."""
    return ReconcilerService(
        storage=storage,
        entity_service=entity_service,
        pipeline=pipeline_service,
        settings=settings,
    )


@pytest.fixture
def watch_service(
    storage: LocalStorage,
    entity_service: EntityService,
    settings: Settings,
) -> WatchService:
    """WatchService with all dependencies."""
    return WatchService(
        storage=storage,
        entity_service=entity_service,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# Async client fixture for FastAPI endpoint tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(
    settings: Settings,
    storage: LocalStorage,
    chunking_service: ChunkingService,
    embedding_service: EmbeddingService,
    index_service: IndexService,
    event_bus: EventBus,
    pipeline_service: PipelineService,
    entity_service: EntityService,
    vfs_service: VfsService,
    reconciler_service: ReconcilerService,
    watch_service: WatchService,
) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the FastAPI app via ASGITransport."""
    from app.main import app

    # Set app.state before the lifespan runs (lifespan will overwrite,
    # but we need it for readiness checks)
    app.state.settings = settings
    app.state.entity_service = entity_service
    app.state.embedding_service = embedding_service
    app.state.index_service = index_service
    app.state.vfs_service = vfs_service
    app.state.reconciler_service = reconciler_service
    app.state.watch_service = watch_service
    app.state.event_bus = event_bus

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup
    await embedding_service.close()
    await watch_service.shutdown()
