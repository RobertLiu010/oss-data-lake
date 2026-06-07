"""End-to-end test: MD file → pipeline → parquet → LanceDB → search.

Verifies the full flow:
1. Upload a Markdown file via EntityService
2. Pipeline runs: source → canonical_md → chunk → embed → parquet → LanceDB
3. Parquet contains text + embedding_text (sliding window context)
4. LanceDB sync preserves both fields
5. Semantic search returns results
6. Version log is written
"""

from __future__ import annotations

import os

os.environ["EMBEDDING_MOCK"] = "1"

import pytest

from app.config import Settings
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.entity_service import EntityService
from app.services.event_bus import EventBus
from app.services.index import IndexService
from app.services.pipeline import PipelineService
from app.storage.local import LocalStorage

# Sample markdown with multiple sections to trigger sliding window
SAMPLE_MD = """\
# Introduction

This is the introduction section of the document. It provides an overview
of the key concepts and sets the stage for the detailed discussion that follows.

# Architecture

The system architecture consists of three main components: the storage layer,
the processing pipeline, and the query engine. Each component is designed
to be independently scalable and fault-tolerant.

# Implementation Details

The implementation uses a combination of Python and Rust for performance-critical
paths. The storage layer is built on top of LanceDB with parquet as the
intermediate format for reliability.

# Testing Strategy

We employ a comprehensive testing strategy that includes unit tests, integration
tests, and end-to-end tests. The test suite is run on every commit to ensure
that regressions are caught early.

# Deployment

The deployment process is fully automated using CI/CD pipelines. We use
blue-green deployments to minimize downtime and canary releases to
gradually roll out changes.
"""


@pytest.fixture
def settings(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    lance_dir = tmp_path / "lance_data"
    lance_dir.mkdir()
    return Settings(
        storage={"backend": "local", "local": {"root": str(data_dir)}},
        lance={"data_dir": str(lance_dir)},
        embedding={"base_url": "http://127.0.0.1:8006", "model": "embedding-v5"},
        vfs={"cache_ttl": 0.0},
    )


@pytest.fixture
def storage(settings):
    return LocalStorage(settings)


@pytest.fixture
def chunking_service(settings):
    return ChunkingService(settings)


@pytest.fixture
def embedding_service(settings):
    return EmbeddingService(settings)


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def index_service(settings):
    return IndexService(settings)


@pytest.fixture
def pipeline_service(storage, chunking_service, embedding_service, index_service, settings, event_bus):
    return PipelineService(
        storage=storage,
        chunking=chunking_service,
        embedding=embedding_service,
        index=index_service,
        settings=settings,
        event_bus=event_bus,
    )


@pytest.fixture
def entity_service(storage, pipeline_service, settings):
    return EntityService(
        storage=storage,
        pipeline=pipeline_service,
        settings=settings,
    )


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------


class TestMdE2E:
    """End-to-end test for the MD pipeline."""

    @pytest.mark.asyncio
    async def test_full_md_pipeline(
        self, entity_service, pipeline_service, index_service, storage, settings,
    ):
        """Full pipeline: create entity → chunk → embed → parquet → LanceDB → search."""
        ws, col = "ws_e2e", "col_e2e"

        # Step 1: Create entity from MD content
        entity = await entity_service.create_from_bytes(
            ws, col, "test.md", SAMPLE_MD.encode("utf-8"),
        )
        assert entity is not None
        assert entity.entity_id.startswith("ent_")
        entity_id = entity.entity_id

        # Step 2: Verify source_original and canonical_md exist
        assert storage.file_exists(ws, col, entity_id, "source_original")
        assert storage.file_exists(ws, col, entity_id, "canonical_md")

        # Step 3: Verify entity manifest
        manifest = storage.read_entity_manifest(ws, col, entity_id)
        assert manifest is not None
        assert manifest["entity_type"] == "document"
        assert manifest["version"] == 1

        # Step 4: Verify version log
        version_log = storage.read_version_log(ws, col, entity_id)
        assert len(version_log) >= 1
        assert version_log[0]["version"] == 1
        assert version_log[0]["trigger"] == "ingest"

        # Step 5: Verify parquet file exists
        parquet_table = index_service.read_entity_parquet(ws, col, entity_id, "canonical_md")
        assert parquet_table is not None
        assert parquet_table.num_rows > 0

        # Step 6: Verify parquet has both text and embedding_text columns
        assert "text" in parquet_table.column_names
        assert "embedding_text" in parquet_table.column_names
        assert "embedding" in parquet_table.column_names

        # Step 7: Verify text != embedding_text for windowed chunks
        # (sliding window means embedding_text includes context from neighbors)
        texts = parquet_table.column("text").to_pylist()
        emb_texts = parquet_table.column("embedding_text").to_pylist()
        assert len(texts) == len(emb_texts)
        # At least some chunks should have embedding_text != text
        # (the middle chunks in a multi-chunk document)
        has_window_context = any(
            len(et) > len(t) for t, et in zip(texts, emb_texts)
        )
        assert has_window_context, (
            "Expected at least some chunks to have embedding_text longer than text "
            "(sliding window context)"
        )

        # Step 8: Verify LanceDB sync — search should work
        # The pipeline uses _enqueue_sync which falls back to direct sync
        # in tests (no SyncQueue). Give it a moment.
        import asyncio
        await asyncio.sleep(0.3)

        # LanceDB table should exist
        assert index_service.table_exists(ws, col)

        # Step 9: Semantic search
        # Mock embeddings produce deterministic vectors based on text
        query_vector = [0.1] * settings.embedding.dimension
        results = await index_service.search(ws, col, query_vector, top_k=3)
        assert len(results) > 0
        # All results should have entity_id
        for r in results:
            assert r.entity_id == entity_id
            assert r.text != ""

        # Step 10: Lexical search
        lexical_results = await index_service.search_lexical(
            ws, col, "architecture", top_k=3,
        )
        assert len(lexical_results) > 0

        # Step 11: Verify LanceDB table has embedding_text column
        table_name = index_service._table_name(ws, col)
        lance_table = index_service.db.open_table(table_name)
        lance_schema = lance_table.schema
        lance_col_names = [f.name for f in lance_schema]
        assert "text" in lance_col_names
        assert "embedding_text" in lance_col_names

    @pytest.mark.asyncio
    async def test_parquet_text_vs_embedding_text(
        self, entity_service, index_service, storage,
    ):
        """Verify that text is the chunk's own text, and embedding_text
        includes sliding window context (3-chunk window)."""
        ws, col = "ws_text", "col_text"

        entity = await entity_service.create_from_bytes(
            ws, col, "multi.md", SAMPLE_MD.encode("utf-8"),
        )
        entity_id = entity.entity_id

        parquet_table = index_service.read_entity_parquet(ws, col, entity_id, "canonical_md")
        assert parquet_table is not None

        texts = parquet_table.column("text").to_pylist()
        emb_texts = parquet_table.column("embedding_text").to_pylist()

        # Each chunk's text should be a subset of its embedding_text
        # (embedding_text contains the window = prev + current + next)
        for i, (t, et) in enumerate(zip(texts, emb_texts)):
            assert t in et, (
                f"Chunk {i}: text should be contained in embedding_text. "
                f"text={t[:50]!r}, embedding_text={et[:80]!r}"
            )

        # For a 5-section document, there should be multiple chunks
        assert len(texts) >= 3, f"Expected >= 3 chunks, got {len(texts)}"

    @pytest.mark.asyncio
    async def test_entity_lifecycle(
        self, entity_service, index_service, storage,
    ):
        """Test full entity lifecycle: create → read → update → delete."""
        ws, col = "ws_lifecycle", "col_lifecycle"

        # Create
        entity = await entity_service.create_from_bytes(
            ws, col, "lifecycle.md", b"# Test\n\nSome content here.",
        )
        entity_id = entity.entity_id

        # Read
        read_entity = await entity_service.get_entity(ws, col, entity_id)
        assert read_entity is not None
        assert read_entity.status.value == "enabled"

        # Update (soft delete)
        from app.models.entity import EntityStatus
        patched = await entity_service.patch_entity(
            ws, col, entity_id, status=EntityStatus.HIDDEN,
        )
        assert patched is not None
        assert patched.status == EntityStatus.HIDDEN

        # Verify version log has 2 entries (ingest + update)
        version_log = storage.read_version_log(ws, col, entity_id)
        assert len(version_log) >= 2
        assert version_log[0]["trigger"] == "ingest"
        assert version_log[1]["trigger"] == "update"

        # Hard delete
        deleted = await entity_service.delete_entity(ws, col, entity_id, hard=True)
        assert deleted is True

        # Verify entity is gone
        read_entity = await entity_service.get_entity(ws, col, entity_id)
        assert read_entity is None

    @pytest.mark.asyncio
    async def test_rebuild_lance_from_parquet(
        self, entity_service, index_service,
    ):
        """Verify LanceDB can be rebuilt from parquet files."""
        ws, col = "ws_rebuild", "col_rebuild"

        entity = await entity_service.create_from_bytes(
            ws, col, "rebuild.md", SAMPLE_MD.encode("utf-8"),
        )
        entity_id = entity.entity_id

        # Wait for sync
        import asyncio
        await asyncio.sleep(0.3)

        # Verify table exists
        assert index_service.table_exists(ws, col)
        original_count = index_service.count_entity_chunks(ws, col, entity_id)
        assert original_count > 0

        # Drop LanceDB table
        index_service.drop_table(ws, col)
        assert not index_service.table_exists(ws, col)

        # Rebuild from parquets
        rebuilt_count = await index_service.rebuild_lance_table(ws, col)
        assert rebuilt_count == original_count
        assert index_service.table_exists(ws, col)

        # Verify search still works
        query_vector = [0.1] * index_service.dimension
        results = await index_service.search(ws, col, query_vector, top_k=3)
        assert len(results) > 0
