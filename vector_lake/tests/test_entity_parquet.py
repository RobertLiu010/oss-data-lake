"""Tests for entity-level parquet persistence in IndexService."""

from __future__ import annotations

import pytest

from app.services.index import IndexService

# Use the default embedding dimension from settings
DIM = 1024


# ---------------------------------------------------------------------------
# write_entity_parquet / read_entity_parquet
# ---------------------------------------------------------------------------


class TestEntityParquet:
    """Entity-level parquet file I/O tests."""

    def test_write_entity_parquet_creates_file(
        self, index_service: IndexService, settings
    ):
        """write_entity_parquet creates _index/{rep_name}.parquet."""
        chunks = [
            {"chunk_index": 0, "text": "hello", "embedding": [0.1] * DIM, "metadata": {}},
            {"chunk_index": 1, "text": "world", "embedding": [0.2] * DIM, "metadata": {}},
        ]
        path = index_service.write_entity_parquet(
            "ws", "col", "ent1", chunks, "canonical_md"
        )
        assert path.exists()
        assert path.name == "canonical_md.parquet"
        assert path.parent.name == "_index"

    def test_write_entity_parquet_data_roundtrip(
        self, index_service: IndexService, settings
    ):
        """Written parquet can be read back with correct data."""
        chunks = [
            {"chunk_index": 0, "text": "hello", "embedding": [0.1] * DIM, "metadata": {"header": "intro"}},
            {"chunk_index": 1, "text": "world", "embedding": [0.2] * DIM, "metadata": {}},
        ]
        index_service.write_entity_parquet("ws", "col", "ent1", chunks, "canonical_md")

        table = index_service.read_entity_parquet("ws", "col", "ent1", "canonical_md")
        assert table is not None
        assert table.num_rows == 2
        assert table.column("text")[0].as_py() == "hello"
        assert table.column("chunk_index")[1].as_py() == 1

    def test_read_entity_parquet_missing_returns_none(
        self, index_service: IndexService, settings
    ):
        """read_entity_parquet returns None for missing file."""
        result = index_service.read_entity_parquet("ws", "col", "noent", "canonical_md")
        assert result is None

    def test_write_multiple_reps(
        self, index_service: IndexService, settings
    ):
        """Multiple rep_names produce separate parquet files."""
        chunks_a = [{"chunk_index": 0, "text": "a", "embedding": [0.1] * DIM, "metadata": {}}]
        chunks_b = [{"chunk_index": 0, "text": "b", "embedding": [0.2] * DIM, "metadata": {}}]

        index_service.write_entity_parquet("ws", "col", "ent1", chunks_a, "canonical_md")
        index_service.write_entity_parquet("ws", "col", "ent1", chunks_b, "page_image")

        reps = index_service.list_entity_parquets("ws", "col", "ent1")
        assert set(reps) == {"canonical_md", "page_image"}

    def test_delete_entity_parquet_specific_rep(
        self, index_service: IndexService, settings
    ):
        """Delete specific rep parquet leaves others intact."""
        chunks = [{"chunk_index": 0, "text": "x", "embedding": [0.1] * DIM, "metadata": {}}]
        index_service.write_entity_parquet("ws", "col", "ent1", chunks, "canonical_md")
        index_service.write_entity_parquet("ws", "col", "ent1", chunks, "page_image")

        index_service.delete_entity_parquet("ws", "col", "ent1", "canonical_md")

        reps = index_service.list_entity_parquets("ws", "col", "ent1")
        assert reps == ["page_image"]

    def test_delete_entity_parquet_all(
        self, index_service: IndexService, settings
    ):
        """Delete all parquets for an entity."""
        chunks = [{"chunk_index": 0, "text": "x", "embedding": [0.1] * DIM, "metadata": {}}]
        index_service.write_entity_parquet("ws", "col", "ent1", chunks, "canonical_md")
        index_service.write_entity_parquet("ws", "col", "ent1", chunks, "page_image")

        index_service.delete_entity_parquet("ws", "col", "ent1")

        reps = index_service.list_entity_parquets("ws", "col", "ent1")
        assert reps == []


# ---------------------------------------------------------------------------
# upsert_chunks writes parquet + syncs to LanceDB
# ---------------------------------------------------------------------------


class TestUpsertWithParquet:
    """upsert_chunks writes parquet file and syncs to LanceDB."""

    @pytest.mark.asyncio
    async def test_upsert_creates_parquet_and_lance(
        self, index_service: IndexService, settings
    ):
        """upsert_chunks writes entity parquet and syncs to LanceDB."""
        chunks = [
            {"chunk_index": 0, "text": "hello world", "embedding": [0.1] * DIM, "metadata": {}},
        ]
        count = await index_service.upsert_chunks(
            "ws", "col", "ent1", chunks, "canonical_md"
        )
        assert count == 1

        # Parquet file exists
        assert index_service.read_entity_parquet("ws", "col", "ent1", "canonical_md") is not None

        # LanceDB table exists and has data
        assert index_service.table_exists("ws", "col")
        assert index_service.count_entity_chunks("ws", "col", "ent1") == 1

    @pytest.mark.asyncio
    async def test_upsert_replaces_parquet(
        self, index_service: IndexService, settings
    ):
        """Second upsert for same (entity, rep) replaces the parquet."""
        chunks_v1 = [
            {"chunk_index": 0, "text": "version 1", "embedding": [0.1] * DIM, "metadata": {}},
        ]
        chunks_v2 = [
            {"chunk_index": 0, "text": "version 2", "embedding": [0.2] * DIM, "metadata": {}},
            {"chunk_index": 1, "text": "extra chunk", "embedding": [0.3] * DIM, "metadata": {}},
        ]
        await index_service.upsert_chunks("ws", "col", "ent1", chunks_v1, "canonical_md")
        await index_service.upsert_chunks("ws", "col", "ent1", chunks_v2, "canonical_md")

        # Parquet should have 2 rows (v2)
        table = index_service.read_entity_parquet("ws", "col", "ent1", "canonical_md")
        assert table is not None
        assert table.num_rows == 2

    @pytest.mark.asyncio
    async def test_upsert_different_reps_separate_parquets(
        self, index_service: IndexService, settings
    ):
        """Different rep_names produce separate parquet files."""
        chunks_a = [
            {"chunk_index": 0, "text": "canonical", "embedding": [0.1] * DIM, "metadata": {}},
        ]
        chunks_b = [
            {"chunk_index": 0, "text": "page image", "embedding": [0.2] * DIM, "metadata": {}},
        ]
        await index_service.upsert_chunks("ws", "col", "ent1", chunks_a, "canonical_md")
        await index_service.upsert_chunks("ws", "col", "ent1", chunks_b, "page_image")

        reps = index_service.list_entity_parquets("ws", "col", "ent1")
        assert set(reps) == {"canonical_md", "page_image"}


# ---------------------------------------------------------------------------
# rebuild_lance_table
# ---------------------------------------------------------------------------


class TestRebuildLanceTable:
    """Rebuild LanceDB table from entity parquets."""

    @pytest.mark.asyncio
    async def test_rebuild_from_parquets(
        self, index_service: IndexService, settings
    ):
        """Rebuild recreates LanceDB table from parquet files."""
        chunks = [
            {"chunk_index": 0, "text": "hello", "embedding": [0.1] * DIM, "metadata": {}},
        ]
        await index_service.upsert_chunks("ws", "col", "ent1", chunks, "canonical_md")

        # Drop LanceDB table
        index_service.drop_table("ws", "col")
        assert not index_service.table_exists("ws", "col")

        # Rebuild from parquets
        count = await index_service.rebuild_lance_table("ws", "col")
        assert count == 1
        assert index_service.table_exists("ws", "col")

    @pytest.mark.asyncio
    async def test_rebuild_empty_collection(
        self, index_service: IndexService, settings
    ):
        """Rebuild with no parquets returns 0."""
        count = await index_service.rebuild_lance_table("ws", "col_empty")
        assert count == 0


# ---------------------------------------------------------------------------
# delete_entity_chunks removes parquet + LanceDB
# ---------------------------------------------------------------------------


class TestDeleteEntityChunks:
    """delete_entity_chunks removes both parquet and LanceDB data."""

    @pytest.mark.asyncio
    async def test_delete_removes_parquet(
        self, index_service: IndexService, settings
    ):
        """Delete removes parquet file."""
        chunks = [
            {"chunk_index": 0, "text": "hello", "embedding": [0.1] * DIM, "metadata": {}},
        ]
        await index_service.upsert_chunks("ws", "col", "ent1", chunks, "canonical_md")

        index_service.delete_entity_chunks("ws", "col", "ent1")
        assert index_service.read_entity_parquet("ws", "col", "ent1", "canonical_md") is None

    @pytest.mark.asyncio
    async def test_get_indexed_entity_ids(
        self, index_service: IndexService, settings
    ):
        """get_indexed_entity_ids scans parquet files."""
        chunks = [
            {"chunk_index": 0, "text": "hello", "embedding": [0.1] * DIM, "metadata": {}},
        ]
        await index_service.upsert_chunks("ws", "col", "ent1", chunks, "canonical_md")
        await index_service.upsert_chunks("ws", "col", "ent2", chunks, "canonical_md")

        ids = index_service.get_indexed_entity_ids("ws", "col")
        assert ids == {"ent1", "ent2"}
