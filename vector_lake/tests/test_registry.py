"""Tests for the Template Registry system.

Covers TemplateRegistry CRUD, lookup, builtin template registration,
MdRepTemplate.build(), VectorIndexTemplate.build(), pipeline integration
with the registry, and EntityService unsupported-extension handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.search import SearchResult
from app.services.entity_service import EntityService
from app.services.pipeline import PipelineService
from app.services.registry import (
    IndexContext,
    RepContext,
    RepResult,
    SearchContext,
    TemplateRegistry,
)
from app.services.templates import (
    MdRepTemplate,
    VectorIndexTemplate,
    register_builtin_templates,
)

# ---------------------------------------------------------------------------
# Helpers – lightweight template stubs for registration tests
# ---------------------------------------------------------------------------


class StubRepTemplate:
    """Minimal RepTemplate-compatible object for testing."""

    name = "stub_rep"
    rep_type = "stub_type"
    source_extensions = [".stub"]
    entity_types: list[str] = []

    async def build(self, ctx: RepContext) -> RepResult:
        return RepResult(content=b"stub", rep_type=self.rep_type)


class StubIndexTemplate:
    """Minimal IndexTemplate-compatible object for testing."""

    name = "stub_index"
    index_type = "stub"

    async def build(self, ctx: IndexContext) -> None:
        pass

    async def search(self, ctx: SearchContext) -> list[SearchResult]:
        return []


# ---------------------------------------------------------------------------
# 1. test_registry_register_rep
# ---------------------------------------------------------------------------


def test_registry_register_rep():
    """Register a custom RepTemplate and verify it can be looked up."""
    reg = TemplateRegistry()
    tmpl = StubRepTemplate()
    reg.register_rep(tmpl)

    found = reg.get_rep_template("stub_rep")
    assert found is tmpl
    assert found.name == "stub_rep"
    assert found.rep_type == "stub_type"


# ---------------------------------------------------------------------------
# 2. test_registry_register_rep_duplicate
# ---------------------------------------------------------------------------


def test_registry_register_rep_duplicate():
    """Registering a RepTemplate with the same name twice raises ValueError."""
    reg = TemplateRegistry()
    reg.register_rep(StubRepTemplate())

    with pytest.raises(ValueError, match="already registered"):
        reg.register_rep(StubRepTemplate())


# ---------------------------------------------------------------------------
# 3. test_registry_unregister_rep
# ---------------------------------------------------------------------------


def test_registry_unregister_rep():
    """Unregister a RepTemplate and verify it is gone."""
    reg = TemplateRegistry()
    reg.register_rep(StubRepTemplate())
    reg.unregister_rep("stub_rep")

    assert reg.get_rep_template("stub_rep") is None
    # Extension map should also be cleaned up
    assert reg.find_rep_templates_for_extension(".stub") == []


# ---------------------------------------------------------------------------
# 4. test_registry_unregister_rep_not_found
# ---------------------------------------------------------------------------


def test_registry_unregister_rep_not_found():
    """Unregistering a non-existent RepTemplate raises KeyError."""
    reg = TemplateRegistry()

    with pytest.raises(KeyError, match="not found"):
        reg.unregister_rep("nonexistent")


# ---------------------------------------------------------------------------
# 5. test_registry_find_rep_by_extension
# ---------------------------------------------------------------------------


def test_registry_find_rep_by_extension():
    """Find templates that handle a given file extension."""
    reg = TemplateRegistry()
    md_tmpl = MdRepTemplate()
    reg.register_rep(md_tmpl)

    found = reg.find_rep_templates_for_extension(".md")
    assert len(found) == 1
    assert found[0] is md_tmpl


def test_registry_find_rep_by_extension_case_insensitive():
    """Extension lookup should be case-insensitive."""
    reg = TemplateRegistry()
    reg.register_rep(MdRepTemplate())

    found = reg.find_rep_templates_for_extension(".MD")
    assert len(found) == 1


# ---------------------------------------------------------------------------
# 6. test_registry_find_rep_by_filename
# ---------------------------------------------------------------------------


def test_registry_find_rep_by_filename():
    """Find template for a full filename by extracting its extension."""
    reg = TemplateRegistry()
    md_tmpl = MdRepTemplate()
    reg.register_rep(md_tmpl)

    found = reg.find_rep_template_for_file("test.md")
    assert found is md_tmpl


def test_registry_find_rep_by_filename_nested_path():
    """find_rep_template_for_file works with paths containing dots."""
    reg = TemplateRegistry()
    md_tmpl = MdRepTemplate()
    reg.register_rep(md_tmpl)

    found = reg.find_rep_template_for_file("docs/my.notes.file.md")
    assert found is md_tmpl


# ---------------------------------------------------------------------------
# 7. test_registry_find_rep_unknown_extension
# ---------------------------------------------------------------------------


def test_registry_find_rep_unknown_extension():
    """Unknown extension returns empty list for extension lookup."""
    reg = TemplateRegistry()

    found = reg.find_rep_templates_for_extension(".xyz")
    assert found == []


def test_registry_find_rep_unknown_filename():
    """Unknown filename extension returns None for file lookup."""
    reg = TemplateRegistry()

    found = reg.find_rep_template_for_file("document.xyz")
    assert found is None


# ---------------------------------------------------------------------------
# 8. test_registry_register_index
# ---------------------------------------------------------------------------


def test_registry_register_index():
    """Register a custom IndexTemplate and verify it can be looked up."""
    reg = TemplateRegistry()
    tmpl = StubIndexTemplate()
    reg.register_index(tmpl)

    found = reg.get_index_template("stub_index")
    assert found is tmpl
    assert found.index_type == "stub"


def test_registry_register_index_duplicate():
    """Registering an IndexTemplate with the same name twice raises ValueError."""
    reg = TemplateRegistry()
    reg.register_index(StubIndexTemplate())

    with pytest.raises(ValueError, match="already registered"):
        reg.register_index(StubIndexTemplate())


def test_registry_unregister_index():
    """Unregister an IndexTemplate and verify it is gone."""
    reg = TemplateRegistry()
    reg.register_index(StubIndexTemplate())
    reg.unregister_index("stub_index")

    assert reg.get_index_template("stub_index") is None


def test_registry_unregister_index_not_found():
    """Unregistering a non-existent IndexTemplate raises KeyError."""
    reg = TemplateRegistry()

    with pytest.raises(KeyError, match="not found"):
        reg.unregister_index("nonexistent")


# ---------------------------------------------------------------------------
# 9. test_registry_list_templates
# ---------------------------------------------------------------------------


def test_registry_list_templates():
    """list_rep_templates and list_index_templates return all registered templates."""
    reg = TemplateRegistry()
    reg.register_rep(MdRepTemplate())
    reg.register_rep(StubRepTemplate())
    reg.register_index(VectorIndexTemplate())
    reg.register_index(StubIndexTemplate())

    rep_list = reg.list_rep_templates()
    assert len(rep_list) == 2
    rep_names = {r["name"] for r in rep_list}
    assert rep_names == {"md_to_canonical", "stub_rep"}

    # Verify dict structure for rep templates
    md_entry = next(r for r in rep_list if r["name"] == "md_to_canonical")
    assert md_entry["rep_type"] == "canonical_md"
    assert md_entry["source_extensions"] == [".md"]
    assert md_entry["entity_types"] == []

    index_list = reg.list_index_templates()
    assert len(index_list) == 2
    index_names = {i["name"] for i in index_list}
    assert index_names == {"vector_index", "stub_index"}

    # Verify dict structure for index templates
    vec_entry = next(i for i in index_list if i["name"] == "vector_index")
    assert vec_entry["index_type"] == "vector"


# ---------------------------------------------------------------------------
# 10. test_md_rep_template_build
# ---------------------------------------------------------------------------


async def test_md_rep_template_build():
    """MdRepTemplate.build() returns RepResult with canonical_md content and metadata."""
    tmpl = MdRepTemplate()
    content = b"# Hello World\n\nSome markdown content."

    mock_storage = MagicMock()
    ctx = RepContext(
        workspace_id="ws-1",
        collection_id="col-1",
        entity_id="ent-1",
        filename="test.md",
        source_content=content,
        storage=mock_storage,
        settings=MagicMock(),
    )

    result = await tmpl.build(ctx)

    assert isinstance(result, RepResult)
    assert result.rep_type == "canonical_md"
    assert result.content == content  # pass-through for .md
    assert result.metadata["transform"] == "parse"
    assert result.metadata["modality"] == "text"
    assert "content_hash" in result.metadata
    assert "input_content_hash" in result.metadata

    # storage.save_file should have been called for source_original
    mock_storage.save_file.assert_called_once_with(
        "ws-1", "col-1", "ent-1", "source_original", content,
    )


# ---------------------------------------------------------------------------
# 11. test_vector_index_template_build
# ---------------------------------------------------------------------------


async def test_vector_index_template_build():
    """VectorIndexTemplate.build() delegates to index_service.upsert_chunks."""
    tmpl = VectorIndexTemplate()

    mock_index_service = AsyncMock()
    chunks = [
        {"chunk_index": 0, "text": "hello", "embedding": [0.1, 0.2], "metadata": {}},
    ]
    ctx = IndexContext(
        workspace_id="ws-1",
        collection_id="col-1",
        entity_id="ent-1",
        chunks=chunks,
        index_service=mock_index_service,
        settings=MagicMock(),
    )

    await tmpl.build(ctx)

    mock_index_service.upsert_chunks.assert_awaited_once_with(
        "ws-1", "col-1", "ent-1", chunks,
    )


async def test_vector_index_template_search_semantic():
    """VectorIndexTemplate.search() defaults to semantic search with query_vector."""
    tmpl = VectorIndexTemplate()

    mock_index_service = AsyncMock()
    mock_index_service.search.return_value = [
        SearchResult(entity_id="ent-1", chunk_index=0, text="hello", score=0.9),
    ]
    ctx = SearchContext(
        workspace_id="ws-1",
        collection_id="col-1",
        query="hello",
        query_vector=[0.1, 0.2],
        top_k=5,
        index_service=mock_index_service,
        settings=MagicMock(),
    )

    results = await tmpl.search(ctx)

    assert len(results) == 1
    assert results[0].entity_id == "ent-1"
    mock_index_service.search.assert_awaited_once()


async def test_vector_index_template_search_lexical():
    """VectorIndexTemplate.search() with search_type=lexical uses lexical search."""
    tmpl = VectorIndexTemplate()

    mock_index_service = AsyncMock()
    mock_index_service.search_lexical.return_value = []
    ctx = SearchContext(
        workspace_id="ws-1",
        collection_id="col-1",
        query="hello",
        top_k=5,
        index_service=mock_index_service,
        settings=MagicMock(),
        params={"search_type": "lexical"},
    )

    results = await tmpl.search(ctx)
    assert results == []
    mock_index_service.search_lexical.assert_awaited_once()


# ---------------------------------------------------------------------------
# 12. test_register_builtin_templates
# ---------------------------------------------------------------------------


def test_register_builtin_templates():
    """register_builtin_templates() registers both MdRepTemplate and VectorIndexTemplate
    into the global registry singleton."""
    from app.services.registry import registry

    # Clear the global registry to ensure a clean state for this test
    registry._rep_templates.clear()
    registry._index_templates.clear()
    registry._extension_map.clear()
    registry._steps.clear()
    registry._dag.clear()
    registry._extension_format_map.clear()

    register_builtin_templates()

    # Verify rep template
    md_tmpl = registry.get_rep_template("md_to_canonical")
    assert md_tmpl is not None
    assert isinstance(md_tmpl, MdRepTemplate)
    assert md_tmpl.rep_type == "canonical_md"

    # Verify index template
    vec_tmpl = registry.get_index_template("vector_index")
    assert vec_tmpl is not None
    assert isinstance(vec_tmpl, VectorIndexTemplate)
    assert vec_tmpl.index_type == "vector"

    # Verify extension mapping works
    found = registry.find_rep_template_for_file("example.md")
    assert found is md_tmpl

    # Verify listing
    rep_list = registry.list_rep_templates()
    assert any(r["name"] == "md_to_canonical" for r in rep_list)
    index_list = registry.list_index_templates()
    assert any(i["name"] == "vector_index" for i in index_list)

    # Re-register should raise ValueError (already registered)
    with pytest.raises(ValueError, match="already registered"):
        register_builtin_templates()


# ---------------------------------------------------------------------------
# 13. test_pipeline_process_entity_generic
# ---------------------------------------------------------------------------


async def test_pipeline_process_entity_generic(
    storage, chunking_service, embedding_service, index_service, settings, event_bus,
):
    """PipelineService.process_entity() works with a fresh registry containing
    the builtin templates."""
    reg = TemplateRegistry()
    reg.register_rep(MdRepTemplate())
    reg.register_index(VectorIndexTemplate())

    pipeline = PipelineService(
        storage=storage,
        chunking=chunking_service,
        embedding=embedding_service,
        index=index_service,
        settings=settings,
        event_bus=event_bus,
        template_registry=reg,
    )

    md_content = "# Registry Test\n\nContent processed via registry-driven pipeline."
    chunks = await pipeline.process_entity(
        workspace_id="ws-reg",
        collection_id="col-reg",
        entity_id="ent-reg",
        filename="doc.md",
        source_content=md_content.encode("utf-8"),
    )

    assert len(chunks) > 0

    # Verify storage files were created
    source = storage.read_file("ws-reg", "col-reg", "ent-reg", "source_original")
    assert source is not None
    assert source.decode("utf-8") == md_content

    canonical = storage.read_file("ws-reg", "col-reg", "ent-reg", "canonical_md")
    assert canonical is not None
    assert canonical.decode("utf-8") == md_content

    # Verify index was populated
    count = index_service.count_entity_chunks("ws-reg", "col-reg", "ent-reg")
    assert count == len(chunks)


# ---------------------------------------------------------------------------
# 14. test_entity_create_unsupported_extension
# ---------------------------------------------------------------------------


async def test_entity_create_unsupported_extension(
    storage, pipeline_service, settings,
):
    """EntityService.create_from_bytes() with an unsupported file extension
    raises ValueError."""
    # Use a fresh (empty) registry so no templates are registered
    empty_registry = TemplateRegistry()

    entity_svc = EntityService(
        storage=storage,
        pipeline=pipeline_service,
        settings=settings,
        template_registry=empty_registry,
    )

    with pytest.raises(ValueError, match="No RepTemplate registered"):
        await entity_svc.create_from_bytes(
            workspace_id="ws-unsup",
            collection_id="col-unsup",
            filename="document.xyz",
            content=b"some content",
        )
