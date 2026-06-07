"""Tests for app.services.chunking — ChunkingService, MarkdownSplitter, TableDetector."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services.chunking import ChunkingService, MarkdownSplitter, TableDetector, _truncate_center


# ---------------------------------------------------------------------------
# MarkdownSplitter
# ---------------------------------------------------------------------------


class TestMarkdownSplitter:
    """MarkdownSplitter.split_by_headers tests."""

    def test_splits_by_h1(self):
        md = "# Title 1\nContent 1\n# Title 2\nContent 2"
        chunks = MarkdownSplitter.split_by_headers(md)
        assert len(chunks) == 2
        assert chunks[0]["header"] == "Title 1"
        assert chunks[1]["header"] == "Title 2"

    def test_splits_by_h2(self):
        md = "## Section A\nText A\n## Section B\nText B"
        chunks = MarkdownSplitter.split_by_headers(md)
        assert len(chunks) == 2
        assert chunks[0]["header"] == "Section A"
        assert chunks[0]["level"] == 2

    def test_content_before_first_header(self):
        md = "Intro text\n# First Header\nBody"
        chunks = MarkdownSplitter.split_by_headers(md)
        assert len(chunks) == 2
        # First chunk has no header (intro)
        assert chunks[0]["header"] is None
        assert "Intro" in chunks[0]["text"]

    def test_empty_input(self):
        assert MarkdownSplitter.split_by_headers("") == []

    def test_single_header_no_body(self):
        md = "# Just a header"
        chunks = MarkdownSplitter.split_by_headers(md)
        assert len(chunks) == 1
        assert chunks[0]["header"] == "Just a header"

    def test_multiple_levels(self):
        md = "# H1\nBody1\n## H2\nBody2\n### H3\nBody3"
        chunks = MarkdownSplitter.split_by_headers(md)
        levels = [c["level"] for c in chunks]
        assert 1 in levels
        assert 2 in levels
        assert 3 in levels


# ---------------------------------------------------------------------------
# TableDetector
# ---------------------------------------------------------------------------


class TestTableDetector:
    """TableDetector.find_tables tests."""

    def test_finds_simple_table(self):
        md = "Some text\n| A | B |\n|---|---|\n| 1 | 2 |\nMore text"
        tables = TableDetector.find_tables(md)
        assert len(tables) == 1
        assert "A" in tables[0]["content"]
        assert tables[0]["start"] == 1
        assert tables[0]["end"] == 3

    def test_no_table(self):
        md = "Just plain text\nNo tables here"
        tables = TableDetector.find_tables(md)
        assert len(tables) == 0

    def test_multiple_tables(self):
        md = (
            "| T1 |\n|---|\n| a |\n\nText between\n\n"
            "| T2 |\n|---|\n| b |"
        )
        tables = TableDetector.find_tables(md)
        assert len(tables) == 2

    def test_table_at_end_of_file(self):
        md = "Text\n| A |\n|---|\n| 1 |"
        tables = TableDetector.find_tables(md)
        assert len(tables) == 1

    def test_is_inside_table(self):
        tables = [{"start": 2, "end": 5, "content": "table"}]
        assert TableDetector.is_inside_table(3, tables) is True
        assert TableDetector.is_inside_table(0, tables) is False
        assert TableDetector.is_inside_table(6, tables) is False


# ---------------------------------------------------------------------------
# _truncate_center
# ---------------------------------------------------------------------------


class TestTruncateCenter:
    """_truncate_center keeps center portion."""

    def test_short_text_unchanged(self):
        text = "short"
        assert _truncate_center(text, 100) == text

    def test_exact_length_unchanged(self):
        text = "a" * 10
        assert _truncate_center(text, 10) == text

    def test_truncation_keeps_center(self):
        text = "0123456789"
        result = _truncate_center(text, 4)
        assert len(result) == 4
        # Center of "0123456789" with max_length=4: start=(10-4)//2=3
        assert result == "3456"

    def test_truncation_odd_difference(self):
        text = "0123456789"  # len=10
        result = _truncate_center(text, 5)
        assert len(result) == 5
        # start=(10-5)//2=2
        assert result == "23456"


# ---------------------------------------------------------------------------
# ChunkingService.execute()
# ---------------------------------------------------------------------------


class TestChunkingServiceExecute:
    """Integration tests for ChunkingService.execute()."""

    @pytest.fixture
    def svc(self) -> ChunkingService:
        settings = Settings(chunking={"chunk_tokens": 64, "window_size": 3})
        return ChunkingService(settings)

    @pytest.mark.asyncio
    async def test_returns_chunks_with_embedding_text(self, svc: ChunkingService):
        md = "# Title\nSome content here for chunking.\n## Section\nMore content."
        chunks = await svc.execute(md)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.embedding_text  # non-empty
            assert chunk.text  # non-empty

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self, svc: ChunkingService):
        chunks = await svc.execute("")
        assert chunks == []

    @pytest.mark.asyncio
    async def test_single_line_input(self, svc: ChunkingService):
        chunks = await svc.execute("Just a single line of text.")
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_metadata_propagated(self, svc: ChunkingService):
        md = "# Header\nContent"
        chunks = await svc.execute(md, metadata={"entity_id": "e1"})
        assert len(chunks) > 0
        assert chunks[0].metadata.get("entity_id") == "e1"

    @pytest.mark.asyncio
    async def test_long_document_produces_multiple_chunks(self, svc: ChunkingService):
        # Create a document long enough to produce multiple chunks
        sections = []
        for i in range(20):
            sections.append(f"# Section {i}\n" + "Word " * 200)
        md = "\n".join(sections)
        chunks = await svc.execute(md)
        assert len(chunks) > 1
