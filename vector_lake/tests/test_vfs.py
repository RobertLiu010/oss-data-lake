"""Tests for app.services.vfs — VfsService."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.services.vfs import VfsService
from app.storage.local import LocalStorage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_entity(
    storage: LocalStorage,
    ws: str = "ws1",
    col: str = "col1",
    entity_id: str = "ent1",
    name: str = "doc.md",
    source_content: str = "# Hello\nWorld",
    canonical_content: str = "# Hello\nWorld",
) -> None:
    """Create a minimal entity with source_original + canonical_md + manifest."""
    storage.save_file(ws, col, entity_id, "source_original", source_content.encode())
    storage.save_file(ws, col, entity_id, "canonical_md", canonical_content.encode())
    manifest = {
        "entity_id": entity_id,
        "workspace_id": ws,
        "collection_id": col,
        "entity_type": "document",
        "name": name,
        "source_type": "oss",
        "source_uri": f"local://{ws}/{col}/{entity_id}/source_original",
        "content_hash": "abc",
        "version": 1,
        "status": "enabled",
        "labels": [],
        "model_version": "v5",
        "created_at": "2025-01-01",
        "updated_at": "2025-01-01",
    }
    storage.save_entity_manifest(ws, col, entity_id, manifest)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVfsLs:
    """ls lists entities and files."""

    def test_ls_root_lists_entities(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        _create_entity(storage, entity_id="ent2", name="doc2.md")
        entries = vfs_service.ls("ws1", "col1", "/")
        names = [e.name for e in entries]
        assert "doc1.md" in names
        assert "doc2.md" in names

    def test_ls_entity_dir_lists_reps(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        entries = vfs_service.ls("ws1", "col1", "/doc1.md")
        rep_names = [e.name for e in entries]
        assert "original" in rep_names
        assert "canonical.md" in rep_names

    def test_ls_empty_collection(self, vfs_service: VfsService):
        entries = vfs_service.ls("ws1", "col1", "/")
        assert entries == []


class TestVfsStat:
    """stat returns metadata."""

    def test_stat_entity_dir(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        result = vfs_service.stat("ws1", "col1", "/doc1.md")
        assert result is not None
        assert result.type == "dir"
        assert result.entity_id == "ent1"

    def test_stat_file(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        result = vfs_service.stat("ws1", "col1", "/doc1.md/canonical.md")
        assert result is not None
        assert result.type == "file"
        assert result.rep_type == "canonical_md"

    def test_stat_nonexistent(self, vfs_service: VfsService):
        result = vfs_service.stat("ws1", "col1", "/nonexistent")
        assert result is None


class TestVfsRead:
    """read returns file content."""

    def test_read_canonical(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(
            storage,
            entity_id="ent1",
            name="doc1.md",
            canonical_content="# Hello World",
        )
        result = vfs_service.read("ws1", "col1", "/doc1.md/canonical.md")
        assert result is not None
        content, entity_id, rep_type = result
        assert "Hello World" in content
        assert entity_id == "ent1"
        assert rep_type == "canonical_md"

    def test_read_original(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(
            storage,
            entity_id="ent1",
            name="doc1.md",
            source_content="Original content",
        )
        result = vfs_service.read("ws1", "col1", "/doc1.md/original")
        assert result is not None
        content, _, _ = result
        assert "Original content" in content

    def test_read_nonexistent_file(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        result = vfs_service.read("ws1", "col1", "/doc1.md/nonexistent")
        assert result is None

    def test_read_dir_returns_none(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        result = vfs_service.read("ws1", "col1", "/doc1.md")
        assert result is None  # dirs are not readable


class TestVfsGlob:
    """glob matches patterns."""

    def test_glob_all_md(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        _create_entity(storage, entity_id="ent2", name="doc2.md")
        entries = vfs_service.glob("ws1", "col1", "**/*.md")
        paths = [e.path for e in entries]
        assert any("canonical.md" in p for p in paths)

    def test_glob_specific_file(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        entries = vfs_service.glob("ws1", "col1", "**/canonical.md")
        assert len(entries) >= 1
        for e in entries:
            assert e.name == "canonical.md"

    def test_glob_no_match(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        entries = vfs_service.glob("ws1", "col1", "**/*.pdf")
        assert entries == []


class TestVfsGrep:
    """grep finds text with context."""

    def test_grep_finds_match(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(
            storage,
            entity_id="ent1",
            name="doc1.md",
            canonical_content="# Title\nSome important text here\nMore lines",
        )
        matches = vfs_service.grep("ws1", "col1", "important")
        assert len(matches) >= 1
        assert "important" in matches[0].line_text

    def test_grep_with_context(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(
            storage,
            entity_id="ent1",
            name="doc1.md",
            canonical_content="line1\nline2\nTARGET LINE\nline4\nline5",
        )
        matches = vfs_service.grep("ws1", "col1", "TARGET", context_lines=2)
        assert len(matches) >= 1
        m = matches[0]
        assert len(m.context_before) <= 2
        assert len(m.context_after) <= 2

    def test_grep_no_match(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(
            storage,
            entity_id="ent1",
            name="doc1.md",
            canonical_content="Nothing to see here",
        )
        matches = vfs_service.grep("ws1", "col1", "nonexistent_pattern_xyz")
        assert matches == []

    def test_grep_invalid_regex(self, vfs_service: VfsService, storage: LocalStorage):
        _create_entity(storage, entity_id="ent1", name="doc1.md")
        # Invalid regex should return empty list, not crash
        matches = vfs_service.grep("ws1", "col1", "[invalid")
        assert matches == []


class TestVfsCache:
    """Cache invalidation works."""

    def test_cache_invalidation(self, storage: LocalStorage, tmp_path: Path):
        # Use a non-zero TTL to test caching
        settings = Settings(
            storage={"backend": "local", "local": {"root": str(tmp_path / "data")}},
            vfs={"cache_ttl": 60.0},
        )
        svc = VfsService(LocalStorage(settings), settings)

        _create_entity(svc.storage, entity_id="ent1", name="doc1.md")
        # First call populates cache
        entries1 = svc.ls("ws1", "col1", "/")
        assert len(entries1) == 1

        # Add another entity
        _create_entity(svc.storage, entity_id="ent2", name="doc2.md")
        # Cache still returns old result
        entries2 = svc.ls("ws1", "col1", "/")
        assert len(entries2) == 1  # still cached

        # Invalidate and re-query
        svc.invalidate_cache("ws1", "col1")
        entries3 = svc.ls("ws1", "col1", "/")
        assert len(entries3) == 2

    def test_invalidate_all_cache(self, storage: LocalStorage, tmp_path: Path):
        settings = Settings(
            storage={"backend": "local", "local": {"root": str(tmp_path / "data")}},
            vfs={"cache_ttl": 60.0},
        )
        svc = VfsService(LocalStorage(settings), settings)
        _create_entity(svc.storage, entity_id="ent1", name="doc1.md")
        svc.ls("ws1", "col1", "/")
        assert len(svc._cache) > 0
        svc.invalidate_all_cache()
        assert len(svc._cache) == 0
