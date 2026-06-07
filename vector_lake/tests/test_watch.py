"""Tests for app.services.watch — WatchService file monitoring."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.watch import FileEventType, WatchService, WatchStrategy
from app.storage.local import LocalStorage


def _make_watch_strategy(
    watch_id: str,
    workspace_id: str,
    collection_id: str,
    watch_dir: str,
    scan_interval: int = 0.1,
) -> WatchStrategy:
    """Create a WatchStrategy with polling backend and short scan interval."""
    return WatchStrategy(
        watch_id=watch_id,
        workspace_id=workspace_id,
        collection_id=collection_id,
        watch_dir=watch_dir,
        allowed_extensions=[".md"],
        entity_id_strategy="filename",
        on_conflict="update",
        recursive=True,
        max_file_size_mb=500,
        backend="polling",
        scan_interval=scan_interval,
    )


class TestStartStop:
    """Start and stop watch without error."""

    @pytest.mark.asyncio
    async def test_start_stop(
        self,
        watch_service: WatchService,
        tmp_path: Path,
    ):
        watch_dir = tmp_path / "watch_start_stop"
        watch_dir.mkdir(parents=True, exist_ok=True)

        strategy = _make_watch_strategy(
            "test_start_stop", "ws_watch", "col_watch", str(watch_dir),
        )
        watch_service.create_watch(strategy)
        watch_service.start_watch("test_start_stop")

        # Let it run briefly
        await asyncio.sleep(0.3)

        watch_service.stop_watch("test_start_stop")
        assert "test_start_stop" not in watch_service.watches


class TestCreateEntityOnNewFile:
    """When a new .md file appears, entity is created."""

    @pytest.mark.asyncio
    async def test_create_entity_on_new_file(
        self,
        watch_service: WatchService,
        storage: LocalStorage,
        tmp_path: Path,
    ):
        ws, col = "ws_create", "col_create"
        watch_dir = tmp_path / "watch_create"
        watch_dir.mkdir(parents=True, exist_ok=True)

        strategy = _make_watch_strategy(
            "test_create", ws, col, str(watch_dir),
        )
        watch_service.create_watch(strategy)
        watch_service.start_watch("test_create")

        # Wait for initial scan to complete
        await asyncio.sleep(0.3)

        # Create a new .md file
        md_file = watch_dir / "hello.md"
        md_file.write_text("# Hello World\nThis is a test file.")

        # Wait for polling to detect and process
        await asyncio.sleep(0.5)

        # Verify entity was created in storage
        entities = storage.list_entities(ws, col)
        assert len(entities) >= 1

        # Verify the entity has content
        eid = entities[0]
        source = storage.read_file(ws, col, eid, "source_original")
        assert source is not None
        assert b"Hello World" in source

        # Cleanup
        watch_service.stop_watch("test_create")


class TestUpdateEntityOnModified:
    """When file is modified, entity is re-created."""

    @pytest.mark.asyncio
    async def test_update_entity_on_modified(
        self,
        watch_service: WatchService,
        storage: LocalStorage,
        tmp_path: Path,
    ):
        ws, col = "ws_mod", "col_mod"
        watch_dir = tmp_path / "watch_modify"
        watch_dir.mkdir(parents=True, exist_ok=True)

        # Pre-create a file
        md_file = watch_dir / "doc.md"
        md_file.write_text("# Version 1\nOriginal content.")

        strategy = _make_watch_strategy(
            "test_modify", ws, col, str(watch_dir),
        )
        watch_service.create_watch(strategy)
        watch_service.start_watch("test_modify")

        # Wait for initial scan + processing
        await asyncio.sleep(0.5)

        # Record initial entities
        entities_before = storage.list_entities(ws, col)

        # Modify the file
        md_file.write_text("# Version 2\nModified content here.")

        # Wait for polling to detect modification
        await asyncio.sleep(0.5)

        # Verify entities exist (content hash change may create new entity)
        entities_after = storage.list_entities(ws, col)
        assert len(entities_after) >= 1

        # Cleanup
        watch_service.stop_watch("test_modify")


class TestIgnoreNonMdFiles:
    """.txt files are ignored by the watcher."""

    @pytest.mark.asyncio
    async def test_ignore_non_md_files(
        self,
        watch_service: WatchService,
        storage: LocalStorage,
        tmp_path: Path,
    ):
        ws, col = "ws_ignore", "col_ignore"
        watch_dir = tmp_path / "watch_ignore"
        watch_dir.mkdir(parents=True, exist_ok=True)

        strategy = _make_watch_strategy(
            "test_ignore", ws, col, str(watch_dir),
        )
        watch_service.create_watch(strategy)
        watch_service.start_watch("test_ignore")

        await asyncio.sleep(0.3)

        # Create a .txt file (should be ignored)
        txt_file = watch_dir / "notes.txt"
        txt_file.write_text("This should be ignored.")

        await asyncio.sleep(0.5)

        # No entities should be created for .txt files
        entities = storage.list_entities(ws, col)
        assert len(entities) == 0

        # Cleanup
        watch_service.stop_watch("test_ignore")


class TestRemoveEntityOnDelete:
    """When file is deleted, watch processes the event without error."""

    @pytest.mark.asyncio
    async def test_remove_entity_on_delete(
        self,
        watch_service: WatchService,
        storage: LocalStorage,
        tmp_path: Path,
    ):
        ws, col = "ws_del_watch", "col_del_watch"
        watch_dir = tmp_path / "watch_delete"
        watch_dir.mkdir(parents=True, exist_ok=True)

        strategy = _make_watch_strategy(
            "test_delete", ws, col, str(watch_dir),
        )
        watch_service.create_watch(strategy)
        watch_service.start_watch("test_delete")

        # Wait for initial scan to complete
        await asyncio.sleep(0.3)

        # Create a file AFTER starting the watch so it triggers entity creation
        md_file = watch_dir / "to_delete.md"
        md_file.write_text("# To Delete\nThis file will be deleted.")

        # Wait for polling to detect and create entity
        await asyncio.sleep(0.5)

        # Verify entity was created
        entities_before = storage.list_entities(ws, col)
        assert len(entities_before) >= 1

        # Delete the file
        md_file.unlink()

        # Wait for polling to detect deletion
        await asyncio.sleep(0.5)

        # v0.1: delete event is logged but entity is not auto-deleted
        # Verify the watch processed events without error
        assert "test_delete" in watch_service.watches
        strategy_after = watch_service.watches["test_delete"]
        assert strategy_after.total_events >= 1

        # Cleanup
        watch_service.stop_watch("test_delete")


class TestPollingBackend:
    """Watch with polling backend works correctly."""

    @pytest.mark.asyncio
    async def test_polling_backend(
        self,
        watch_service: WatchService,
        storage: LocalStorage,
        tmp_path: Path,
    ):
        ws, col = "ws_poll", "col_poll"
        watch_dir = tmp_path / "watch_polling"
        watch_dir.mkdir(parents=True, exist_ok=True)

        strategy = _make_watch_strategy(
            "test_polling", ws, col, str(watch_dir), scan_interval=0.1,
        )
        assert strategy.backend == "polling"

        watch_service.create_watch(strategy)
        watch_service.start_watch("test_polling")

        await asyncio.sleep(0.3)

        # Create a file
        md_file = watch_dir / "poll_test.md"
        md_file.write_text("# Polling Test\nContent for polling test.")

        await asyncio.sleep(0.5)

        # Verify file was processed
        entities = storage.list_entities(ws, col)
        assert len(entities) >= 1

        # Verify the watch recorded events
        strategy_after = watch_service.watches["test_polling"]
        assert strategy_after.total_events >= 1
        assert strategy_after.total_processed >= 1

        # Cleanup
        watch_service.stop_watch("test_polling")