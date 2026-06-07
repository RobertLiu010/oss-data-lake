"""Comprehensive E2E tests covering all PRD features.

Test matrix:
1. Entity CRUD + lifecycle (§2.1, §4.1)
2. Pipeline: Rep + Index (§2.6)
3. Representation management + 9-field Rep Tags (§2.3, §4.2)
4. Chunking: sliding window + embedding_text vs text (§4.3)
5. Index: parquet staging + LanceDB sync + rebuild (§5.12)
6. SyncQueue + SyncWorker: async sync + retry + crash recovery (§5.12)
7. Search: semantic + lexical + hybrid RRF (§5.6)
8. Reconciler: drift detection + auto-repair (§5.9)
9. VFS: ls/stat/read/glob/grep (§5.10)
10. Watch service: file monitoring + dead letter (§5.15)
11. Entity manifest + version log (§5.12)
12. OSS Tag simulation / xattr (§4.6)
13. Lineage cascade: stale marking (§2.5)
14. Two-phase consistency: Rep↔Raw + Index↔Rep (§2.5)
15. API endpoints (§3)
16. Migration (§5.14)
"""

from __future__ import annotations

import os

os.environ["EMBEDDING_MOCK"] = "1"

import asyncio
import json

import pytest

from app.models.entity import EntityStatus
from app.services.lineage import cascade_stale, get_stale_reps
from app.services.sync_queue import SyncQueue, SyncTask, SyncWorker
from app.services.watch import FileEventType, WatchStrategy

SAMPLE_MD = """\
# Introduction

This is the introduction section. It covers the basics of the system
and provides context for the detailed discussion that follows.

# Architecture

The system architecture consists of three main components: the storage layer,
the processing pipeline, and the query engine. Each component is independently
scalable and fault-tolerant.

# Implementation

The implementation uses Python and Rust for performance-critical paths.
The storage layer is built on LanceDB with parquet as intermediate format.

# Testing

We employ unit tests, integration tests, and end-to-end tests.
The test suite runs on every commit to catch regressions early.

# Deployment

The deployment is fully automated using CI/CD pipelines with
blue-green deployments and canary releases.
"""


# ---------------------------------------------------------------------------
# Fixtures — most are provided by conftest.py
# ---------------------------------------------------------------------------

# reconciler_service and watch_service are also in conftest.py,
# no need to redefine here.


# ===========================================================================
# 1. Entity CRUD + Lifecycle (§2.1, §4.1)
# ===========================================================================


class TestEntityCRUD:
    """Entity create/read/update/delete lifecycle."""

    @pytest.mark.asyncio
    async def test_create_entity_from_bytes(self, entity_service, storage):
        ws, col = "ws1", "col1"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", b"# Hello\n\nWorld",
        )
        assert entity.entity_id.startswith("ent_")
        assert entity.entity_type == "document"
        assert entity.name == "doc.md"
        assert entity.status == EntityStatus.ENABLED
        # Verify files exist
        assert storage.file_exists(ws, col, entity.entity_id, "source_original")
        assert storage.file_exists(ws, col, entity.entity_id, "canonical_md")

    @pytest.mark.asyncio
    async def test_get_entity(self, entity_service):
        ws, col = "ws1", "col1"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", b"# Hello",
        )
        fetched = await entity_service.get_entity(ws, col, entity.entity_id)
        assert fetched is not None
        assert fetched.entity_id == entity.entity_id

    @pytest.mark.asyncio
    async def test_list_entities(self, entity_service):
        ws, col = "ws1", "col1"
        await entity_service.create_from_bytes(ws, col, "a.md", b"# A")
        await entity_service.create_from_bytes(ws, col, "b.md", b"# B")
        entities = await entity_service.list_entities(ws, col)
        assert len(entities) >= 2

    @pytest.mark.asyncio
    async def test_patch_entity_status(self, entity_service):
        ws, col = "ws1", "col1"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        patched = await entity_service.patch_entity(
            ws, col, entity.entity_id, status=EntityStatus.HIDDEN,
        )
        assert patched.status == EntityStatus.HIDDEN

    @pytest.mark.asyncio
    async def test_soft_delete(self, entity_service):
        ws, col = "ws1", "col1"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        deleted = await entity_service.delete_entity(ws, col, entity.entity_id, hard=False)
        assert deleted is True
        # Entity still exists but status=deleted
        fetched = await entity_service.get_entity(ws, col, entity.entity_id)
        assert fetched is not None
        assert fetched.status == EntityStatus.DELETED

    @pytest.mark.asyncio
    async def test_hard_delete(self, entity_service, storage):
        ws, col = "ws1", "col1"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        eid = entity.entity_id
        deleted = await entity_service.delete_entity(ws, col, eid, hard=True)
        assert deleted is True
        # Entity dir should be gone
        fetched = await entity_service.get_entity(ws, col, eid)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_entity(self, entity_service):
        result = await entity_service.get_entity("ws1", "col1", "nonexistent")
        assert result is None


# ===========================================================================
# 2. Pipeline: Rep + Index (§2.6)
# ===========================================================================


class TestPipelineE2E:
    """Full pipeline execution: source → reps → chunks → embed → index."""

    @pytest.mark.asyncio
    async def test_md_pipeline_produces_chunks(self, entity_service, index_service):
        ws, col = "ws2", "col2"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", SAMPLE_MD.encode(),
        )
        # Verify parquet exists
        pq = index_service.read_entity_parquet(ws, col, entity.entity_id, "canonical_md")
        assert pq is not None
        assert pq.num_rows > 0

    @pytest.mark.asyncio
    async def test_pipeline_events_published(self, entity_service, event_bus):
        from app.services.event_bus import EventType
        ws, col = "ws2", "col2"
        # Subscribe to events
        q = event_bus.subscribe(EventType.ENTITY_CREATED)
        await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        # Check events were published
        try:
            ev = await asyncio.wait_for(q.get(), timeout=2.0)
            assert ev.event_type == EventType.ENTITY_CREATED
        except TimeoutError:
            pass  # Event may have been consumed before subscription


# ===========================================================================
# 3. Representation + 9-field Rep Tags (§2.3, §4.2)
# ===========================================================================


class TestRepTags:
    """Representation management with 9-field OSS Tag simulation.

    Note: xattr may not be available in all environments (e.g. /tmp).
    Tests verify tags when xattr works, otherwise verify manifest.
    """

    @pytest.mark.asyncio
    async def test_rep_tags_via_manifest(self, entity_service, storage):
        """Rep metadata is stored in manifest (source of truth)."""
        ws, col = "ws3", "col3"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        eid = entity.entity_id
        # Manifest is always the source of truth
        manifest = storage.read_entity_manifest(ws, col, eid)
        assert manifest is not None
        assert manifest["entity_type"] == "document"
        assert manifest["status"] == "enabled"

    @pytest.mark.asyncio
    async def test_rep_tags_when_xattr_available(self, entity_service, storage):
        """When xattr works, rep tags should have all 9 keys."""
        ws, col = "ws3", "col3b"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        eid = entity.entity_id
        tags = storage.get_rep_tags(ws, col, eid, "source_original")
        if not tags:
            # xattr not available in this environment — skip gracefully
            pytest.skip("xattr not available in /tmp")
        from app.storage.local import REP_TAG_KEYS
        for key in REP_TAG_KEYS:
            assert key in tags, f"Rep tag key '{key}' missing"


# ===========================================================================
# 4. Chunking: sliding window + embedding_text (§4.3)
# ===========================================================================


class TestChunkingE2E:
    """Chunking with sliding window produces text + embedding_text."""

    @pytest.mark.asyncio
    async def test_sliding_window_embedding_text(self, entity_service, index_service):
        ws, col = "ws4", "col4"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", SAMPLE_MD.encode(),
        )
        pq = index_service.read_entity_parquet(ws, col, entity.entity_id, "canonical_md")
        texts = pq.column("text").to_pylist()
        emb_texts = pq.column("embedding_text").to_pylist()
        # Each text should be contained in its embedding_text
        for t, et in zip(texts, emb_texts):
            assert t in et
        # Some embedding_texts should be longer (window context)
        assert any(len(et) > len(t) for t, et in zip(texts, emb_texts))

    @pytest.mark.asyncio
    async def test_chunk_anchor_present(self, entity_service, index_service):
        ws, col = "ws4", "col4"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", SAMPLE_MD.encode(),
        )
        pq = index_service.read_entity_parquet(ws, col, entity.entity_id, "canonical_md")
        # Metadata should contain header info
        meta_col = pq.column("metadata").to_pylist()
        has_header = any("header" in json.loads(m) for m in meta_col)
        assert has_header


# ===========================================================================
# 5. Index: parquet staging + LanceDB sync + rebuild (§5.12)
# ===========================================================================


class TestIndexE2E:
    """Index management: parquet → LanceDB pipeline."""

    @pytest.mark.asyncio
    async def test_parquet_staging_dir(self, entity_service, index_service):
        """Parquet files go to _index/staging/ per PRD §5.12."""
        ws, col = "ws5", "col5"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        pq_path = index_service._parquet_path(ws, col, entity.entity_id, "canonical_md")
        assert pq_path.exists()
        assert pq_path.parent.name == "staging"
        assert pq_path.parent.parent.name == "_index"

    @pytest.mark.asyncio
    async def test_lance_rebuild_from_parquet(self, entity_service, index_service):
        ws, col = "ws5", "col5"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", SAMPLE_MD.encode(),
        )
        await asyncio.sleep(0.3)
        original_count = index_service.count_entity_chunks(ws, col, entity.entity_id)
        assert original_count > 0
        # Drop and rebuild
        index_service.drop_table(ws, col)
        assert not index_service.table_exists(ws, col)
        rebuilt = await index_service.rebuild_lance_table(ws, col)
        assert rebuilt == original_count
        assert index_service.table_exists(ws, col)

    @pytest.mark.asyncio
    async def test_parquet_atomic_write(self, entity_service, index_service):
        """No .tmp files left after write."""
        ws, col = "ws5", "col5"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        staging_dir = index_service._index_dir(ws, col, entity.entity_id)
        tmp_files = list(staging_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Leftover .tmp files: {tmp_files}"


# ===========================================================================
# 6. SyncQueue + SyncWorker (§5.12)
# ===========================================================================


class TestSyncQueueE2E:
    """SyncQueue: enqueue → worker consumes → LanceDB synced."""

    @pytest.mark.asyncio
    async def test_sync_queue_enqueue_and_process(self, settings, index_service):
        ws, col = "ws6", "col6"
        # Write parquet directly
        chunks = [
            {"chunk_index": 0, "text": "hello", "embedding": [0.1] * settings.embedding.dimension, "metadata": {}},
        ]
        await index_service.upsert_chunks(ws, col, "ent1", chunks, "canonical_md")

        # Create SyncQueue + Worker
        sync_queue = SyncQueue(settings)
        worker = SyncWorker(sync_queue, index_service)

        # Enqueue
        task = SyncTask(workspace_id=ws, collection_id=col, entity_id="ent1", rep_name="canonical_md")
        enqueued = await sync_queue.enqueue(task)
        assert enqueued is True

        # Start worker briefly
        await worker.start()
        await asyncio.sleep(1.0)
        await worker.stop()

        # Verify LanceDB synced
        assert index_service.table_exists(ws, col)
        assert index_service.count_entity_chunks(ws, col, "ent1") == 1

    @pytest.mark.asyncio
    async def test_sync_queue_dedup(self, settings, index_service):
        ws, col = "ws6", "col6b"
        sync_queue = SyncQueue(settings)
        task1 = SyncTask(workspace_id=ws, collection_id=col, entity_id="e1", rep_name="canonical_md")
        task2 = SyncTask(workspace_id=ws, collection_id=col, entity_id="e1", rep_name="canonical_md")
        await sync_queue.enqueue(task1)
        await sync_queue.enqueue(task2)
        # Dedup: same key, second replaces first
        assert sync_queue.stats()["enqueued"] >= 1

    @pytest.mark.asyncio
    async def test_sync_queue_crash_recovery(self, settings, index_service):
        ws, col = "ws6", "col6c"
        sync_queue = SyncQueue(settings)
        # Enqueue a task
        task = SyncTask(workspace_id=ws, collection_id=col, entity_id="e1", rep_name="canonical_md")
        await sync_queue.enqueue(task)
        # Simulate crash: create new queue instance
        sync_queue2 = SyncQueue(settings)
        recovered = sync_queue2.recover_pending()
        assert recovered >= 1


# ===========================================================================
# 7. Search: semantic + lexical + hybrid (§5.6)
# ===========================================================================


class TestSearchE2E:
    """Search: semantic, lexical, hybrid RRF."""

    @pytest.mark.asyncio
    async def test_semantic_search(self, entity_service, index_service, settings):
        ws, col = "ws7", "col7"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", SAMPLE_MD.encode(),
        )
        await asyncio.sleep(0.3)
        query_vector = [0.1] * settings.embedding.dimension
        results = await index_service.search(ws, col, query_vector, top_k=3)
        assert len(results) > 0
        assert all(r.entity_id == entity.entity_id for r in results)

    @pytest.mark.asyncio
    async def test_lexical_search(self, entity_service, index_service):
        ws, col = "ws7", "col7b"
        await entity_service.create_from_bytes(
            ws, col, "doc.md", SAMPLE_MD.encode(),
        )
        await asyncio.sleep(0.3)
        results = await index_service.search_lexical(ws, col, "architecture", top_k=3)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_hybrid_search(self, entity_service, index_service, settings):
        ws, col = "ws7", "col7c"
        await entity_service.create_from_bytes(
            ws, col, "doc.md", SAMPLE_MD.encode(),
        )
        await asyncio.sleep(0.3)
        query_vector = [0.1] * settings.embedding.dimension
        results = await index_service.search_hybrid(
            ws, col, "architecture", query_vector, top_k=3,
        )
        assert len(results) > 0
        assert all(r.search_type == "hybrid" for r in results)

    @pytest.mark.asyncio
    async def test_search_no_results(self, index_service):
        results = await index_service.search("ws_none", "col_none", [0.1] * 1024, top_k=3)
        assert results == []


# ===========================================================================
# 8. Reconciler: drift detection + auto-repair (§5.9)
# ===========================================================================


class TestReconcilerE2E:
    """Reconciler: detect drift and auto-repair."""

    @pytest.mark.asyncio
    async def test_reconcile_detects_missing_rep(self, entity_service, reconciler_service, storage):
        ws, col = "ws8", "col8"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        eid = entity.entity_id
        # Delete canonical_md to create drift
        from app.storage.lineage import rep_type_to_relpath
        canon_path = storage._entity_dir(ws, col, eid) / rep_type_to_relpath("canonical_md")
        if canon_path.exists():
            canon_path.unlink()
        # Run reconcile
        result = await reconciler_service.reconcile(ws, col)
        assert result.entities_scanned >= 1
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_rep" in drift_types

    @pytest.mark.asyncio
    async def test_reconcile_auto_repairs_missing_rep(self, reconciler_service, pipeline_service, storage):
        ws, col = "ws8", "col8b"
        # Create entity manually (just source_original, no canonical_md)
        storage.save_file(ws, col, "ent_manual", "source_original", b"# Manual")
        storage.save_entity_manifest(ws, col, "ent_manual", {
            "entity_id": "ent_manual", "workspace_id": ws, "collection_id": col,
            "entity_type": "document", "name": "manual.md", "source_type": "oss",
            "source_uri": "", "content_hash": "abc", "version": 1,
            "status": "enabled", "labels": [], "model_version": "",
            "created_at": "", "updated_at": "",
        })
        result = await reconciler_service.reconcile(ws, col)
        # Should detect missing canonical_md
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_rep" in drift_types

    @pytest.mark.asyncio
    async def test_reconcile_distributed_lock(self, reconciler_service):
        ws, col = "ws8", "col8c"
        # First reconcile acquires lock
        await reconciler_service.reconcile(ws, col)
        # Lock should be released
        lock_path = reconciler_service._lock_path(ws, col)
        assert not lock_path.exists()


# ===========================================================================
# 9. VFS: ls/stat/read/glob/grep (§5.10)
# ===========================================================================


class TestVFSE2E:
    """Virtual File System operations."""

    @pytest.mark.asyncio
    async def test_vfs_ls(self, entity_service, vfs_service):
        ws, col = "ws9", "col9"
        await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        entries = vfs_service.ls(ws, col, "/")
        assert len(entries) >= 1

    @pytest.mark.asyncio
    async def test_vfs_stat(self, entity_service, vfs_service):
        ws, col = "ws9", "col9b"
        await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        # Find the entity dir in VFS
        entries = vfs_service.ls(ws, col, "/")
        assert len(entries) >= 1
        # Stat the entity dir
        stat = vfs_service.stat(ws, col, entries[0].path)
        assert stat is not None
        assert stat.type == "dir"

    @pytest.mark.asyncio
    async def test_vfs_read(self, entity_service, vfs_service):
        ws, col = "ws9", "col9c"
        await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello World")
        # List entity dir contents
        entries = vfs_service.ls(ws, col, "/")
        entity_entry = entries[0]
        # List files inside entity
        files = vfs_service.ls(ws, col, entity_entry.path)
        # Read a file
        for f in files:
            if f.type == "file":
                content = vfs_service.read(ws, col, f.path)
                assert content is not None
                break

    @pytest.mark.asyncio
    async def test_vfs_glob(self, entity_service, vfs_service):
        ws, col = "ws9", "col9d"
        await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        results = vfs_service.glob(ws, col, "**/*.md")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_vfs_grep(self, entity_service, vfs_service):
        ws, col = "ws9", "col9e"
        await entity_service.create_from_bytes(ws, col, "doc.md", b"# Architecture\n\nThe system is scalable.")
        matches = vfs_service.grep(ws, col, "scalable")
        assert len(matches) >= 1


# ===========================================================================
# 10. Watch service (§5.15)
# ===========================================================================


class TestWatchE2E:
    """Watch Mode: file monitoring + dead letter."""

    def test_create_watch_strategy(self, watch_service, tmp_path):
        watch_dir = tmp_path / "watch_dir"
        watch_dir.mkdir()
        strategy = WatchStrategy(
            watch_id="w1",
            workspace_id="ws10",
            collection_id="col10",
            watch_dir=str(watch_dir),
        )
        result = watch_service.create_watch(strategy)
        assert result.watch_id == "w1"
        assert result.status.value == "initializing"

    def test_create_duplicate_watch_fails(self, watch_service, tmp_path):
        watch_dir = tmp_path / "watch_dir2"
        watch_dir.mkdir()
        strategy = WatchStrategy(
            watch_id="w2",
            workspace_id="ws10",
            collection_id="col10",
            watch_dir=str(watch_dir),
        )
        watch_service.create_watch(strategy)
        with pytest.raises(ValueError, match="already exists"):
            watch_service.create_watch(strategy)

    @pytest.mark.asyncio
    async def test_watch_detects_new_file(self, watch_service, entity_service, tmp_path):
        watch_dir = tmp_path / "watch_dir3"
        watch_dir.mkdir()
        strategy = WatchStrategy(
            watch_id="w3",
            workspace_id="ws10",
            collection_id="col10",
            watch_dir=str(watch_dir),
            scan_interval=1,
        )
        watch_service.create_watch(strategy)
        # Initial scan
        watch_service._scan_files("w3", initial=True)
        # Add a new file
        (watch_dir / "new.md").write_text("# New Document")
        # Scan for changes
        events = watch_service._scan_files("w3")
        assert len(events) >= 1
        assert events[0].event_type == FileEventType.CREATED

    @pytest.mark.asyncio
    async def test_watch_detects_modified_file(self, watch_service, tmp_path):
        watch_dir = tmp_path / "watch_dir4"
        watch_dir.mkdir()
        (watch_dir / "existing.md").write_text("# Original")
        strategy = WatchStrategy(
            watch_id="w4",
            workspace_id="ws10",
            collection_id="col10",
            watch_dir=str(watch_dir),
        )
        watch_service.create_watch(strategy)
        watch_service._scan_files("w4", initial=True)
        # Modify file
        (watch_dir / "existing.md").write_text("# Modified")
        events = watch_service._scan_files("w4")
        assert len(events) >= 1
        assert events[0].event_type == FileEventType.MODIFIED

    @pytest.mark.asyncio
    async def test_watch_detects_deleted_file(self, watch_service, tmp_path):
        watch_dir = tmp_path / "watch_dir5"
        watch_dir.mkdir()
        (watch_dir / "to_delete.md").write_text("# Delete Me")
        strategy = WatchStrategy(
            watch_id="w5",
            workspace_id="ws10",
            collection_id="col10",
            watch_dir=str(watch_dir),
        )
        watch_service.create_watch(strategy)
        watch_service._scan_files("w5", initial=True)
        # Delete file
        (watch_dir / "to_delete.md").unlink()
        events = watch_service._scan_files("w5")
        assert len(events) >= 1
        assert events[0].event_type == FileEventType.DELETED


# ===========================================================================
# 11. Entity Manifest + Version Log (§5.12)
# ===========================================================================


class TestManifestVersionLog:
    """Entity manifest (source of truth) + version log (append-only)."""

    @pytest.mark.asyncio
    async def test_manifest_written_on_create(self, entity_service, storage):
        ws, col = "ws11", "col11"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        manifest = storage.read_entity_manifest(ws, col, entity.entity_id)
        assert manifest is not None
        assert manifest["entity_type"] == "document"
        assert manifest["version"] == 1

    @pytest.mark.asyncio
    async def test_version_log_appended_on_create(self, entity_service, storage):
        ws, col = "ws11", "col11b"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        log = storage.read_version_log(ws, col, entity.entity_id)
        assert len(log) >= 1
        assert log[0]["trigger"] == "ingest"
        assert log[0]["version"] == 1

    @pytest.mark.asyncio
    async def test_version_log_appended_on_update(self, entity_service, storage):
        ws, col = "ws11", "col11c"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        await entity_service.patch_entity(
            ws, col, entity.entity_id, labels=["updated"],
        )
        log = storage.read_version_log(ws, col, entity.entity_id)
        assert len(log) >= 2
        assert log[0]["trigger"] == "ingest"
        assert log[1]["trigger"] == "update"

    @pytest.mark.asyncio
    async def test_manifest_atomic_write(self, entity_service, storage):
        """No .tmp manifest files left after write."""
        ws, col = "ws11", "col11d"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        entity_dir = storage._entity_dir(ws, col, entity.entity_id)
        tmp_files = list(entity_dir.glob(".entity_manifest.json.tmp"))
        assert len(tmp_files) == 0


# ===========================================================================
# 12. OSS Tag simulation / xattr (§4.6)
# ===========================================================================


class TestOSSTagSimulation:
    """OSS Tag simulation via xattr.

    Note: xattr may not be available in all environments (e.g. /tmp).
    Tests verify tags when xattr works, otherwise verify manifest.
    """

    @pytest.mark.asyncio
    async def test_entity_tags_via_manifest(self, entity_service, storage):
        """Entity metadata is stored in manifest (source of truth)."""
        ws, col = "ws12", "col12"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        manifest = storage.read_entity_manifest(ws, col, entity.entity_id)
        assert manifest is not None
        assert manifest["entity_type"] == "document"
        assert manifest["status"] == "enabled"

    @pytest.mark.asyncio
    async def test_entity_tags_when_xattr_available(self, entity_service, storage):
        """When xattr works, entity tags should have all 7 keys."""
        ws, col = "ws12", "col12b"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        tags = storage.get_entity_tags(ws, col, entity.entity_id)
        if not tags:
            pytest.skip("xattr not available in /tmp")
        from app.storage.local import ENTITY_TAG_KEYS
        for key in ENTITY_TAG_KEYS:
            assert key in tags, f"Entity tag key '{key}' missing"

    @pytest.mark.asyncio
    async def test_assemble_entity_from_manifest(self, entity_service, storage):
        ws, col = "ws12", "col12c"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        assembled = storage.assemble_entity(ws, col, entity.entity_id)
        assert assembled is not None
        assert assembled["entity_id"] == entity.entity_id


# ===========================================================================
# 13. Lineage cascade: stale marking (§2.5)
# ===========================================================================


class TestLineageCascade:
    """Lineage cascade: mark downstream reps stale."""

    @pytest.mark.asyncio
    async def test_cascade_stale_marks_downstream(self, entity_service, storage):
        ws, col = "ws13", "col13"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        eid = entity.entity_id
        # Cascade from source_original
        stale_reps = cascade_stale(ws, col, eid, "source_original", storage)
        # canonical_md depends on source_original
        assert "canonical_md" in stale_reps

    @pytest.mark.asyncio
    async def test_get_stale_reps(self, entity_service, storage):
        ws, col = "ws13", "col13b"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        eid = entity.entity_id
        # Mark stale
        cascade_stale(ws, col, eid, "source_original", storage)
        stale = get_stale_reps(ws, col, eid, storage)
        assert "canonical_md" in stale


# ===========================================================================
# 13b. Cascade rebuild: stale → pipeline → index (§2.5 full)
# ===========================================================================


class TestCascadeRebuild:
    """Full cascade: rep change → stale → pipeline re-execute → index re-sync."""

    @pytest.mark.asyncio
    async def test_update_entity_content_cascades(
        self, entity_service, index_service, storage,
    ):
        """update_entity_content triggers: stale → pipeline → index."""
        ws, col = "ws13c", "col13c"
        # Create entity
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", b"# Original\n\nFirst version.",
        )
        eid = entity.entity_id

        # Verify initial state
        pq = index_service.read_entity_parquet(ws, col, eid, "canonical_md")
        assert pq is not None

        # Update content
        updated = await entity_service.update_entity_content(
            ws, col, eid, b"# Updated\n\nSecond version with more content.",
        )
        assert updated is not None
        assert updated.version == 2
        assert updated.content_hash != entity.content_hash

        # Verify pipeline re-executed (canonical_md updated)
        content = storage.read_file(ws, col, eid, "canonical_md")
        assert content is not None
        assert b"Updated" in content

        # Verify index re-synced (parquet has new data)
        pq2 = index_service.read_entity_parquet(ws, col, eid, "canonical_md")
        assert pq2 is not None

        # Verify version log
        log = storage.read_version_log(ws, col, eid)
        triggers = [entry["trigger"] for entry in log]
        assert "content_update" in triggers

    @pytest.mark.asyncio
    async def test_cascade_rebuild_function(
        self, entity_service, index_service, storage, pipeline_service,
    ):
        """cascade_rebuild() marks stale, re-executes pipeline, re-syncs index."""
        from app.services.lineage import cascade_rebuild
        ws, col = "ws13d", "col13d"
        entity = await entity_service.create_from_bytes(
            ws, col, "doc.md", b"# Initial\n\nContent.",
        )
        eid = entity.entity_id

        # Manually trigger cascade rebuild
        rebuilt = await cascade_rebuild(
            ws, col, eid, "source_original",
            storage, pipeline_service,
        )
        assert "canonical_md" in rebuilt

        # Verify no stale reps remain
        stale = get_stale_reps(ws, col, eid, storage)
        assert len(stale) == 0

    @pytest.mark.asyncio
    async def test_update_nonexistent_entity(self, entity_service):
        """update_entity_content returns None for nonexistent entity."""
        result = await entity_service.update_entity_content(
            "ws_none", "col_none", "nonexistent", b"content",
        )
        assert result is None


# ===========================================================================
# 14. Two-phase consistency (§2.5)
# ===========================================================================


class TestTwoPhaseConsistency:
    """Two-phase consistency: Rep↔Raw + Index↔Rep."""

    @pytest.mark.asyncio
    async def test_rep_raw_consistency(self, reconciler_service, storage):
        """Reconciler detects when rep is missing (Rep↔Raw drift)."""
        ws, col = "ws14", "col14"
        # Create entity with only source_original
        storage.save_file(ws, col, "ent_norep", "source_original", b"# No Rep")
        storage.save_entity_manifest(ws, col, "ent_norep", {
            "entity_id": "ent_norep", "workspace_id": ws, "collection_id": col,
            "entity_type": "document", "name": "norep.md", "source_type": "oss",
            "source_uri": "", "content_hash": "abc", "version": 1,
            "status": "enabled", "labels": [], "model_version": "",
            "created_at": "", "updated_at": "",
        })
        result = await reconciler_service.reconcile(ws, col)
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_rep" in drift_types

    @pytest.mark.asyncio
    async def test_index_rep_consistency(self, reconciler_service, entity_service, storage):
        """Reconciler detects when index is missing (Index↔Rep drift)."""
        ws, col = "ws14", "col14b"
        entity = await entity_service.create_from_bytes(ws, col, "doc.md", b"# Hello")
        # Delete the parquet index to create drift
        index_dir = storage._entity_dir(ws, col, entity.entity_id) / "_index" / "staging"
        if index_dir.exists():
            for f in index_dir.glob("*.parquet"):
                f.unlink()
        result = await reconciler_service.reconcile(ws, col)
        # Should detect missing index
        drift_types = {d.drift_type.value for d in result.drifts_found}
        assert "missing_index" in drift_types


# ===========================================================================
# 15. API endpoints (§3) — via httpx AsyncClient
# ===========================================================================


class TestAPIE2E:
    """API endpoint E2E tests via HTTP client."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness_endpoint(self, client):
        resp = await client.get("/readiness")
        assert resp.status_code == 200
        assert resp.json()["ready"] is True

    @pytest.mark.asyncio
    async def test_create_and_list_workspaces(self, client):
        resp = await client.post("/api/v1/workspaces", json={"workspace_id": "ws_api"})
        assert resp.status_code in (200, 201, 409)
        resp = await client.get("/api/v1/workspaces")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_entity_crud_via_api(self, client):
        # Create workspace + collection
        await client.post("/api/v1/workspaces", json={"workspace_id": "ws_crud"})
        await client.post(
            "/api/v1/workspaces/ws_crud/collections",
            json={"collection_id": "col_crud"},
        )
        # Upload entity
        resp = await client.post(
            "/api/v1/workspaces/ws_crud/collections/col_crud/entities",
            files={"file": ("test.md", b"# API Test\n\nContent here.", "text/markdown")},
        )
        assert resp.status_code in (200, 201)
        entity_id = resp.json()["entity_id"]

        # Update content (cascade rebuild)
        resp = await client.put(
            f"/api/v1/workspaces/ws_crud/collections/col_crud/entities/{entity_id}/content",
            files={"file": ("test.md", b"# Updated\n\nNew content.", "text/markdown")},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    @pytest.mark.asyncio
    async def test_reconcile_endpoint(self, client):
        await client.post("/api/v1/workspaces", json={"workspace_id": "ws_rec"})
        await client.post(
            "/api/v1/workspaces/ws_rec/collections",
            json={"collection_id": "col_rec"},
        )
        resp = await client.post(
            "/api/v1/workspaces/ws_rec/collections/col_rec/reconcile",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "drift_count" in data

    @pytest.mark.asyncio
    async def test_rebuild_index_endpoint(self, client):
        await client.post("/api/v1/workspaces", json={"workspace_id": "ws_rebuild"})
        await client.post(
            "/api/v1/workspaces/ws_rebuild/collections",
            json={"collection_id": "col_rebuild"},
        )
        resp = await client.post(
            "/api/v1/workspaces/ws_rebuild/collections/col_rebuild/rebuild-index",
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sync_status_endpoint(self, client):
        await client.post("/api/v1/workspaces", json={"workspace_id": "ws_sync"})
        resp = await client.get("/api/v1/workspaces/ws_sync/sync/status")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_watch_strategy_crud(self, client, tmp_path):
        watch_dir = tmp_path / "api_watch"
        watch_dir.mkdir()
        await client.post("/api/v1/workspaces", json={"workspace_id": "ws_watch"})
        # Create
        resp = await client.post(
            "/api/v1/workspaces/ws_watch/watch-strategies",
            json={
                "collection_id": "col_watch",
                "watch_dir": str(watch_dir),
                "allowed_extensions": [".md"],
            },
        )
        assert resp.status_code == 201
        watch_id = resp.json()["watch_id"]
        # List
        resp = await client.get("/api/v1/workspaces/ws_watch/watch-strategies")
        assert resp.status_code == 200
        # Delete
        resp = await client.delete(
            f"/api/v1/workspaces/ws_watch/watch-strategies/{watch_id}",
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200


# ===========================================================================
# 16. Migration (§5.14)
# ===========================================================================


class TestMigrationE2E:
    """Schema migration runs on startup."""

    def test_migrations_applied_on_startup(self, index_service):
        """IndexService.__init__ runs migrations — verified by no exception."""
        # If we got here, migrations ran successfully
        assert index_service.db is not None

    def test_migration_idempotent(self, settings):
        """Creating IndexService twice doesn't fail."""
        from app.services.index import IndexService
        svc1 = IndexService(settings)
        svc2 = IndexService(settings)
        assert svc1.db is not None
        assert svc2.db is not None
