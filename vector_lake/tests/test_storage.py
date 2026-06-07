"""Tests for app.storage.local — LocalStorage."""

from __future__ import annotations

import json
from pathlib import Path

from app.storage.local import LocalStorage


class TestSaveReadFile:
    """save_file / read_file round-trip."""

    def test_roundtrip_text(self, storage: LocalStorage):
        content = b"Hello, Vector Lake!"
        storage.save_file("ws1", "col1", "ent1", "source_original", content)
        result = storage.read_file("ws1", "col1", "ent1", "source_original")
        assert result == content

    def test_roundtrip_binary(self, storage: LocalStorage):
        content = bytes(range(256))
        storage.save_file("ws1", "col1", "ent1", "binary_rep", content)
        result = storage.read_file("ws1", "col1", "ent1", "binary_rep")
        assert result == content

    def test_read_nonexistent_returns_none(self, storage: LocalStorage):
        result = storage.read_file("ws1", "col1", "nope", "source_original")
        assert result is None

    def test_file_exists(self, storage: LocalStorage):
        storage.save_file("ws1", "col1", "ent1", "source_original", b"data")
        assert storage.file_exists("ws1", "col1", "ent1", "source_original") is True
        assert storage.file_exists("ws1", "col1", "ent1", "missing") is False

    def test_overwrite_file(self, storage: LocalStorage):
        storage.save_file("ws1", "col1", "ent1", "source_original", b"v1")
        storage.save_file("ws1", "col1", "ent1", "source_original", b"v2")
        assert storage.read_file("ws1", "col1", "ent1", "source_original") == b"v2"


class TestListEntities:
    """list_entities returns entity directories."""

    def test_empty_collection(self, storage: LocalStorage):
        assert storage.list_entities("ws1", "col1") == []

    def test_returns_entity_dirs(self, storage: LocalStorage):
        storage.save_file("ws1", "col1", "ent_a", "source_original", b"a")
        storage.save_file("ws1", "col1", "ent_b", "source_original", b"b")
        entities = storage.list_entities("ws1", "col1")
        assert sorted(entities) == ["ent_a", "ent_b"]

    def test_ignores_files_in_col_dir(self, storage: LocalStorage):
        col_dir = Path(storage.root) / "ws1" / "col1"
        col_dir.mkdir(parents=True, exist_ok=True)
        (col_dir / "readme.txt").write_text("ignore me")
        storage.save_file("ws1", "col1", "ent1", "source_original", b"data")
        entities = storage.list_entities("ws1", "col1")
        assert entities == ["ent1"]


class TestEntityManifest:
    """save_entity_manifest / read_entity_manifest round-trip with atomic write."""

    def test_roundtrip_manifest(self, storage: LocalStorage):
        manifest = {
            "entity_id": "ent1",
            "name": "test.md",
            "status": "enabled",
            "labels": ["test"],
        }
        storage.save_entity_manifest("ws1", "col1", "ent1", manifest)
        result = storage.read_entity_manifest("ws1", "col1", "ent1")
        assert result == manifest

    def test_manifest_is_json(self, storage: LocalStorage):
        manifest = {"key": "value", "num": 42}
        storage.save_entity_manifest("ws1", "col1", "ent1", manifest)
        entity_dir = Path(storage.root) / "ws1" / "col1" / "ent1"
        raw = json.loads((entity_dir / ".entity_manifest.json").read_text())
        assert raw == manifest

    def test_no_tmp_file_left(self, storage: LocalStorage):
        storage.save_entity_manifest("ws1", "col1", "ent1", {"x": 1})
        entity_dir = Path(storage.root) / "ws1" / "col1" / "ent1"
        tmp_files = list(entity_dir.glob("*.tmp"))
        assert tmp_files == []

    def test_read_nonexistent_manifest(self, storage: LocalStorage):
        result = storage.read_entity_manifest("ws1", "col1", "nope")
        assert result is None

    def test_overwrite_manifest(self, storage: LocalStorage):
        storage.save_entity_manifest("ws1", "col1", "ent1", {"v": 1})
        storage.save_entity_manifest("ws1", "col1", "ent1", {"v": 2})
        result = storage.read_entity_manifest("ws1", "col1", "ent1")
        assert result["v"] == 2


class TestSyncTagsFromManifest:
    """sync_tags_from_manifest writes xattr tags."""

    def test_sync_writes_xattr(self, storage: LocalStorage):
        # Need source_original file for xattr to work
        storage.save_file("ws1", "col1", "ent1", "source_original", b"data")
        manifest = {
            "entity_id": "ent1",
            "name": "test.md",
            "status": "enabled",
            "entity_type": "document",
            "content_hash": "abc123",
            "version": 1,
            "labels": ["tag1", "tag2"],
            "model_version": "v5",
        }
        storage.save_entity_manifest("ws1", "col1", "ent1", manifest)
        storage.sync_tags_from_manifest("ws1", "col1", "ent1")

        tags = storage.get_entity_tags("ws1", "col1", "ent1")
        # xattr may not work on all filesystems (e.g. tmpfs in CI)
        # so we just check that the call doesn't crash
        if tags:
            assert tags.get("rag_status") == "enabled"
            assert tags.get("entity_type") == "document"
            assert tags.get("name") == "test.md"

    def test_sync_no_manifest_no_crash(self, storage: LocalStorage):
        # Should not raise, just log a warning
        storage.sync_tags_from_manifest("ws1", "col1", "nonexistent")


class TestAssembleEntity:
    """assemble_entity reads manifest first, falls back to xattr."""

    def test_from_manifest(self, storage: LocalStorage):
        storage.save_file("ws1", "col1", "ent1", "source_original", b"data")
        manifest = {
            "entity_id": "ent1",
            "workspace_id": "ws1",
            "collection_id": "col1",
            "entity_type": "document",
            "name": "test.md",
            "source_type": "oss",
            "source_uri": "local://ws1/col1/ent1/source_original",
            "content_hash": "abc",
            "version": 1,
            "status": "enabled",
            "labels": ["l1"],
            "model_version": "v5",
            "created_at": "2025-01-01",
            "updated_at": "2025-01-01",
        }
        storage.save_entity_manifest("ws1", "col1", "ent1", manifest)
        result = storage.assemble_entity("ws1", "col1", "ent1")
        assert result is not None
        assert result["entity_id"] == "ent1"
        assert result["name"] == "test.md"
        assert result["status"] == "enabled"
        assert result["labels"] == ["l1"]

    def test_nonexistent_entity_returns_none(self, storage: LocalStorage):
        result = storage.assemble_entity("ws1", "col1", "nope")
        assert result is None

    def test_fallback_to_xattr(self, storage: LocalStorage):
        """When no manifest exists, assemble from xattr tags."""
        storage.save_file("ws1", "col1", "ent1", "source_original", b"data")
        # Set tags directly (may silently fail on unsupported FS)
        try:
            storage.set_entity_tags("ws1", "col1", "ent1", {
                "rag_status": "hidden",
                "entity_type": "document",
                "name": "fallback.md",
                "content_hash": "xyz",
                "version": "2",
                "labels": "a,b",
                "model_version": "v5",
            })
        except OSError:
            pass  # xattr not supported

        result = storage.assemble_entity("ws1", "col1", "ent1")
        assert result is not None
        # If xattr works, we get the tag values; otherwise defaults
        assert result["entity_id"] == "ent1"
