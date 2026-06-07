"""Tests for EmbeddingService."""

from __future__ import annotations

import math


def test_mock_vector_deterministic(embedding_service):
    """Same text produces the same vector."""
    vec_a = embedding_service._mock_vector("hello world")
    vec_b = embedding_service._mock_vector("hello world")
    assert vec_a == vec_b


def test_mock_vector_different_text(embedding_service):
    """Different texts produce different vectors."""
    vec_a = embedding_service._mock_vector("hello world")
    vec_b = embedding_service._mock_vector("goodbye world")
    assert vec_a != vec_b


def test_mock_vector_dimension(embedding_service):
    """Mock vector has the configured dimension."""
    vec = embedding_service._mock_vector("test")
    assert len(vec) == embedding_service.dimension


def test_mock_vector_normalized(embedding_service):
    """Mock vector is L2-normalized (norm ≈ 1.0)."""
    vec = embedding_service._mock_vector("normalization test")
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-6


async def test_embed_passages_empty(embedding_service):
    """Empty list returns empty list."""
    result = await embedding_service.embed_passages([])
    assert result == []


async def test_embed_passages_mock(embedding_service):
    """Embedding passages in mock mode returns correct number of vectors."""
    texts = ["passage one", "passage two", "passage three"]
    result = await embedding_service.embed_passages(texts)
    assert len(result) == 3
    for vec in result:
        assert len(vec) == embedding_service.dimension


async def test_embed_query_mock(embedding_service):
    """Embedding a single query in mock mode returns a vector."""
    vec = await embedding_service.embed_query("search query")
    assert isinstance(vec, list)
    assert len(vec) == embedding_service.dimension


async def test_embed_passages_batch(embedding_service):
    """Batch embedding with more texts than batch_size still returns all vectors."""
    original_batch_size = embedding_service.batch_size
    embedding_service.batch_size = 2  # force small batches
    try:
        texts = [f"text number {i}" for i in range(7)]
        result = await embedding_service.embed_passages(texts)
        assert len(result) == 7
        for vec in result:
            assert len(vec) == embedding_service.dimension
    finally:
        embedding_service.batch_size = original_batch_size


async def test_close(embedding_service):
    """Closing the service should not raise."""
    await embedding_service.close()
