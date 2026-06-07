"""Tests for app.services.reconciler — ReconcilerService drift detection and repair."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services.entity_service import EntityService
from app.services.pipeline import PipelineService
from app.services.reconciler import DriftType, ReconcilerService
from app.storage.local import LocalStorage


class TestScanNoDrift:
    """Empty collection produces no drifts."""

    @pytest.mark.asyncio
    async def test_scan_no_drift(self, reconciler_service: ReconcilerService):
        ws, col = "ws_scan", "col_empty"
        # Ensure collection dir exists
        col_dir = Path(reconciler_service.root) / ws / col
        col_dir.mkdir(parents=True, exist_ok=True)

        result = await reconciler_service.reconcile(ws, col)
        assert result.entities_scanned == 0
        assert result.drift_count == 0
        assert result.drifts_found == []


class TestScanMissingRep:
    """Entity with source_original but missing canonical_md → MISSING_REP."""

    @pytest.mark.asyncio
    async def test_scan_missing_rep(
        self,
        storage: LocalStorage,
        reconciler_service: ReconcilerService,
    ):
        ws, col, eid = "ws_rep", "col_missing", "ent_missing_rep"
        # Create entity with source_original but no canonical_md
        storage.save_file(ws, col, eid, "source_original", b"# Hello\nContent here")
        storage.save_entity_manifest(ws, col, eid, {
            "entity_id": eid,
            "workspace_id": ws,
            "collection_id": col,
            "entity_type": "document",
            "name": "test.md",
            "source_type": "oss",
            "source_uri": f"local://{ws}/{col}/{eid}/source_original",
            "content_hash": "abc123",
            "version": 1,
            "status": "enabled",
            "labels": [],
            "model_version": "v5",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        })
        storage.sync_tags_from_manifest(ws, col, eid)

        result = await reconciler_service.reconcile(ws, col)
        assert result.entities_scanned == 1
        assert result.drift_count >= 1
        drift_types = {d.drift_type for d in result.drifts_found}
        assert DriftType.MISSING_REP in drift_types


class TestScanMissingIndex:
    """Entity has canonical_md but no LanceDB index → MISSING_INDEX."""

    @pytest.mark.asyncio
    async def test_scan_missing_index(
        self,
        storage: LocalStorage,
        reconciler_service: ReconcilerService,
    ):
        ws, col, eid = "ws_idx", "col_missing_idx", "ent_missing_idx"
        # Create entity with both source_original and canonical_md
        storage.save_file(ws, col, eid, "source_original", b"# Hello\nContent")
        storage.save_file(ws, col, eid, "canonical_md", b"# Hello\nContent")
        storage.save_entity_manifest(ws, col, eid, {
            "entity_id": eid,
            "workspace_id": ws,
            "collection_id": col,
            "entity_type": "document",
            "name": "test.md",
            "source_type": "oss",
            "source_uri": f"local://{ws}/{col}/{eid}/source_original",
            "content_hash": "abc123",
            "version": 1,
            "status": "enabled",
            "labels": [],
            "model_version": "v5",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        })
        storage.sync_tags_from_manifest(ws, col, eid)

        result = await reconciler_service.reconcile(ws, col)
        assert result.entities_scanned == 1
        drift_types = {d.drift_type for d in result.drifts_found}
        assert DriftType.MISSING_INDEX in drift_types


class TestScanOrphanRep:
    """Files outside entity dirs are not scanned as entities."""

    @pytest.mark.asyncio
    async def test_scan_orphan_rep(
        self,
        storage: LocalStorage,
        reconciler_service: ReconcilerService,
    ):
        ws, col = "ws_orphan", "col_orphan"
        col_dir = Path(reconciler_service.root) / ws / col
        col_dir.mkdir(parents=True, exist_ok=True)

        # Create an orphan file directly in the collection dir (not in an entity dir)
        orphan_file = col_dir / "orphan_canonical_md"
        orphan_file.write_text("# Orphan content")

        result = await reconciler_service.reconcile(ws, col)
        # The reconciler only scans directories, so the orphan file is ignored
        assert result.entities_scanned == 0
        assert result.drift_count == 0


class TestRepairCreatesMissingRep:
    """On MISSING_REP, repair calls pipeline to create canonical_md."""

    @pytest.mark.asyncio
    async def test_repair_creates_missing_rep(
        self,
        storage: LocalStorage,
        reconciler_service: ReconcilerService,
    ):
        ws, col, eid = "ws_repair", "col_repair", "ent_repair"
        content = b"# Test Repair\nSome content for repair"
        # Create entity with source_original but no canonical_md
        storage.save_file(ws, col, eid, "source_original", content)
        storage.save_entity_manifest(ws, col, eid, {
            "entity_id": eid,
            "workspace_id": ws,
            "collection_id": col,
            "entity_type": "document",
            "name": "test.md",
            "source_type": "oss",
            "source_uri": f"local://{ws}/{col}/{eid}/source_original",
            "content_hash": "abc123",
            "version": 1,
            "status": "enabled",
            "labels": [],
            "model_version": "v5",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        })
        storage.sync_tags_from_manifest(ws, col, eid)

        # Before reconcile, canonical_md should not exist
        assert not storage.file_exists(ws, col, eid, "canonical_md")

        result = await reconciler_service.reconcile(ws, col)
        assert result.entities_scanned == 1
        # Repair should have created canonical_md
        assert result.drifts_repaired >= 1

        # Verify canonical_md was created
        canonical = storage.read_file(ws, col, eid, "canonical_md")
        assert canonical is not None
        assert b"Test Repair" in canonical


class TestScanMultipleCollections:
    """Multiple collections in workspace are all scanned."""

    @pytest.mark.asyncio
    async def test_scan_multiple_collections(
        self,
        storage: LocalStorage,
        reconciler_service: ReconcilerService,
    ):
        ws = "ws_multi"
        collections = ["col_a", "col_b", "col_c"]
        total_scanned = 0

        for col in collections:
            eid = f"ent_{col}"
            storage.save_file(ws, col, eid, "source_original", b"# Content")
            storage.save_file(ws, col, eid, "canonical_md", b"# Content")
            storage.save_entity_manifest(ws, col, eid, {
                "entity_id": eid,
                "workspace_id": ws,
                "collection_id": col,
                "entity_type": "document",
                "name": "test.md",
                "source_type": "oss",
                "source_uri": f"local://{ws}/{col}/{eid}/source_original",
                "content_hash": "abc123",
                "version": 1,
                "status": "enabled",
                "labels": [],
                "model_version": "v5",
                "created_at": "2025-01-01",
                "updated_at": "2025-01-01",
            })
            storage.sync_tags_from_manifest(ws, col, eid)

            result = await reconciler_service.reconcile(ws, col)
            assert result.entities_scanned == 1
            total_scanned += result.entities_scanned

        assert total_scanned == len(collections)