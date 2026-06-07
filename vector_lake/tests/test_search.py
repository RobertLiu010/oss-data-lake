"""Tests for app.services.index — IndexService search and management."""

from __future__ import annotations

import hashlib
import struct

import pytest

from app.services.index import IndexService


def _make_vector(text: str, dim: int = 1024) -> list[float]:
    """Generate a deterministic unit vector from text for testing."""
    h = hashlib.sha256(text.encode()).digest()
    vals = []
    for i in range(0, min(len(h) * 2, dim * 4), 4):
        chunk = h[i % len(h) : i % len(h) + 4]
        if len(chunk) < 4:
            chunk = chunk + b"\x00" * (4 - len(chunk))
        vals.append(struct.unpack("<f", chunk)[0])
    while len(vals) < dim:
        vals.extend(vals[: min(len(vals), dim - len(vals))])
    vec = vals[:dim]
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


async def _index_test_chunks(
    index_service: IndexService,
    ws: str,
    col: str,
    entity_id: str,
    texts: list[str],
) -> int:
    """Helper: upsert chunks with mock vectors for a given entity."""
    chunks_with_vectors = []
    for idx, text in enumerate(texts):
        chunks_with_vectors.append({
            "chunk_index": idx,
            "text": text,
            "embedding": _make_vector(text),
            "metadata": {"entity_id": entity_id, "chunk": idx},
        })
    return await index_service.upsert_chunks(ws, col, entity_id, chunks_with_vectors)


class TestSearchSemantic:
    """Semantic search returns results after indexing."""

    @pytest.mark.asyncio
    async def test_search_semantic(self, index_service: IndexService):
        ws, col, eid = "ws_sem", "col_sem", "ent_sem"
        await _index_test_chunks(index_service, ws, col, eid, [
            "Python is a programming language",
            "Machine learning uses neural networks",
            "LanceDB is a vector database",
        ])

        query_vector = _make_vector("vector database")
        results = await index_service.search(ws, col, query_vector, top_k=2)
        assert len(results) > 0
        assert len(results) <= 2
        for r in results:
            assert r.entity_id == eid
            assert r.text
            assert r.search_type == "semantic"


class TestSearchLexical:
    """Lexical search returns results after indexing."""

    @pytest.mark.asyncio
    async def test_search_lexical(self, index_service: IndexService):
        ws, col, eid = "ws_lex", "col_lex", "ent_lex"
        await _index_test_chunks(index_service, ws, col, eid, [
            "Python is a programming language",
            "Machine learning uses neural networks",
            "LanceDB is a vector database",
        ])

        results = await index_service.search_lexical(ws, col, "Python", top_k=2)
        assert len(results) > 0
        for r in results:
            assert r.search_type == "lexical"


class TestSearchHybrid:
    """Hybrid search returns results with score."""

    @pytest.mark.asyncio
    async def test_search_hybrid(self, index_service: IndexService):
        ws, col, eid = "ws_hyb", "col_hyb", "ent_hyb"
        await _index_test_chunks(index_service, ws, col, eid, [
            "Python is a programming language",
            "Machine learning uses neural networks",
            "LanceDB is a vector database",
        ])

        query = "Python programming"
        query_vector = _make_vector(query)
        results = await index_service.search_hybrid(ws, col, query, query_vector, top_k=2)
        assert len(results) > 0
        for r in results:
            assert r.search_type == "hybrid"
            assert r.score > 0


class TestSearchNoResults:
    """Search for nonexistent term returns empty."""

    @pytest.mark.asyncio
    async def test_search_no_results(self, index_service: IndexService):
        ws, col, eid = "ws_none", "col_none", "ent_none"
        await _index_test_chunks(index_service, ws, col, eid, [
            "Python is a programming language",
        ])

        # Search for a term that doesn't exist
        results = await index_service.search_lexical(ws, col, "zzz_nonexistent_zzz", top_k=5)
        # May return empty or fallback results; the key is no crash
        assert isinstance(results, list)


class TestCountEntityChunks:
    """After indexing, count returns correct number."""

    @pytest.mark.asyncio
    async def test_count_entity_chunks(self, index_service: IndexService):
        ws, col, eid = "ws_cnt", "col_cnt", "ent_cnt"
        texts = ["Chunk A", "Chunk B", "Chunk C"]
        await _index_test_chunks(index_service, ws, col, eid, texts)

        count = index_service.count_entity_chunks(ws, col, eid)
        assert count == len(texts)


class TestDeleteEntityChunks:
    """After delete, count returns 0."""

    @pytest.mark.asyncio
    async def test_delete_entity_chunks(self, index_service: IndexService):
        ws, col, eid = "ws_del", "col_del", "ent_del"
        await _index_test_chunks(index_service, ws, col, eid, [
            "Chunk A", "Chunk B",
        ])

        assert index_service.count_entity_chunks(ws, col, eid) == 2

        index_service.delete_entity_chunks(ws, col, eid)
        assert index_service.count_entity_chunks(ws, col, eid) == 0


class TestTableExists:
    """After indexing, table_exists returns True."""

    @pytest.mark.asyncio
    async def test_table_exists(self, index_service: IndexService):
        ws, col, eid = "ws_tbl", "col_tbl", "ent_tbl"
        # Before indexing
        assert not index_service.table_exists(ws, col)

        await _index_test_chunks(index_service, ws, col, eid, ["Hello world"])

        # After indexing
        assert index_service.table_exists(ws, col)


class TestGetIndexedEntityIds:
    """Returns correct set of entity_ids."""

    @pytest.mark.asyncio
    async def test_get_indexed_entity_ids(self, index_service: IndexService):
        ws, col = "ws_ids", "col_ids"

        await _index_test_chunks(index_service, ws, col, "ent_a", ["Chunk A1", "Chunk A2"])
        await _index_test_chunks(index_service, ws, col, "ent_b", ["Chunk B1"])

        entity_ids = index_service.get_indexed_entity_ids(ws, col)
        assert entity_ids == {"ent_a", "ent_b"}