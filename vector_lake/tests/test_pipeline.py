"""Tests for PipelineService – MD → canonical_md → chunk → embed → index."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.models.chunk import Chunk
from app.services.event_bus import EventType
from app.services.pipeline import PipelineService

# ---------------------------------------------------------------------------
# 1. Basic happy path
# ---------------------------------------------------------------------------


async def test_process_md_entity_basic(pipeline_service, storage):
    """Happy path: process markdown, get chunks, storage files created, index called."""
    workspace_id = "ws-1"
    collection_id = "col-1"
    entity_id = "ent-1"
    md_content = "# Hello\n\nThis is a test document with some content."

    chunks = await pipeline_service.process_md_entity(
        workspace_id, collection_id, entity_id, md_content,
    )

    # Chunks returned
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    assert all(isinstance(c, Chunk) for c in chunks)

    # Storage files created
    source = storage.read_file(workspace_id, collection_id, entity_id, "source_original")
    assert source is not None
    assert source.decode("utf-8") == md_content

    canonical = storage.read_file(workspace_id, collection_id, entity_id, "canonical_md")
    assert canonical is not None
    assert canonical.decode("utf-8") == md_content

    # Index should have been called – verify chunks are searchable
    count = pipeline_service.index.count_entity_chunks(
        workspace_id, collection_id, entity_id,
    )
    assert count == len(chunks)


# ---------------------------------------------------------------------------
# 2. Empty content
# ---------------------------------------------------------------------------


async def test_process_md_entity_empty_content(pipeline_service):
    """Empty content should return an empty list of chunks."""
    chunks = await pipeline_service.process_md_entity(
        "ws-2", "col-2", "ent-2", "",
    )
    assert chunks == []


# ---------------------------------------------------------------------------
# 3. Embedding failure
# ---------------------------------------------------------------------------


async def test_process_md_entity_embedding_failure(pipeline_service, event_bus):
    """When embedding fails, chunks are returned without vectors and not indexed.
    A REP_COMPLETED event with indexed=False should be published."""
    md_content = "# Test\n\nSome content for embedding failure test."

    # Subscribe to REP_COMPLETED before running
    rep_queue = event_bus.subscribe(EventType.REP_COMPLETED)

    with patch.object(
        pipeline_service.embedding,
        "embed_passages",
        new_callable=AsyncMock,
        side_effect=RuntimeError("embedding service unavailable"),
    ):
        chunks = await pipeline_service.process_md_entity(
            "ws-3", "col-3", "ent-3", md_content,
        )

    # Chunks are still returned (without vectors)
    assert len(chunks) > 0

    # Index should NOT have chunks for this entity
    count = pipeline_service.index.count_entity_chunks("ws-3", "col-3", "ent-3")
    assert count == 0

    # REP_COMPLETED event should have been published
    event = rep_queue.get_nowait()
    assert event.event_type == EventType.REP_COMPLETED
    assert event.entity_id == "ent-3"
    assert event.payload == {"indexed": False}


# ---------------------------------------------------------------------------
# 4. Index failure
# ---------------------------------------------------------------------------


async def test_process_md_entity_index_failure(pipeline_service, event_bus):
    """When index upsert fails, chunks are still returned.
    A REP_COMPLETED event with indexed=False should be published."""
    md_content = "# Test\n\nSome content for index failure test."

    # Subscribe to REP_COMPLETED before running
    rep_queue = event_bus.subscribe(EventType.REP_COMPLETED)

    with patch.object(
        pipeline_service.index,
        "upsert_chunks",
        new_callable=AsyncMock,
        side_effect=RuntimeError("lancedb write error"),
    ):
        chunks = await pipeline_service.process_md_entity(
            "ws-4", "col-4", "ent-4", md_content,
        )

    # Chunks are still returned
    assert len(chunks) > 0

    # REP_COMPLETED event should have been published
    event = rep_queue.get_nowait()
    assert event.event_type == EventType.REP_COMPLETED
    assert event.entity_id == "ent-4"
    assert event.payload == {"indexed": False}


# ---------------------------------------------------------------------------
# 5. Events published on success
# ---------------------------------------------------------------------------


async def test_process_md_entity_events_published(pipeline_service, event_bus):
    """ENTITY_CREATED and INDEX_COMPLETED events should be published on success."""
    md_content = "# Events\n\nContent for event publishing test."

    entity_queue = event_bus.subscribe(EventType.ENTITY_CREATED)
    index_queue = event_bus.subscribe(EventType.INDEX_COMPLETED)

    await pipeline_service.process_md_entity(
        "ws-5", "col-5", "ent-5", md_content,
    )

    # ENTITY_CREATED event
    entity_event = entity_queue.get_nowait()
    assert entity_event.event_type == EventType.ENTITY_CREATED
    assert entity_event.workspace_id == "ws-5"
    assert entity_event.collection_id == "col-5"
    assert entity_event.entity_id == "ent-5"

    # INDEX_COMPLETED event
    index_event = index_queue.get_nowait()
    assert index_event.event_type == EventType.INDEX_COMPLETED
    assert index_event.entity_id == "ent-5"
    assert index_event.payload["chunk_count"] > 0


# ---------------------------------------------------------------------------
# 6. No event bus (None)
# ---------------------------------------------------------------------------


async def test_process_md_entity_no_event_bus(
    storage, chunking_service, embedding_service, index_service, settings,
):
    """Pipeline should work without an event_bus (None) and not crash."""
    pipeline = PipelineService(
        storage=storage,
        chunking=chunking_service,
        embedding=embedding_service,
        index=index_service,
        settings=settings,
        event_bus=None,
    )

    md_content = "# No EventBus\n\nContent without event bus."
    chunks = await pipeline.process_md_entity(
        "ws-6", "col-6", "ent-6", md_content,
    )

    assert len(chunks) > 0

    # Verify storage and index still work
    source = storage.read_file("ws-6", "col-6", "ent-6", "source_original")
    assert source is not None
    assert source.decode("utf-8") == md_content

    count = index_service.count_entity_chunks("ws-6", "col-6", "ent-6")
    assert count == len(chunks)
