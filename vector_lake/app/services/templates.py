"""Built-in templates: MD representation builder and vector index strategy.

These are registered at application startup so the default MD → chunk →
embed → index pipeline works out of the box.  Additional templates can be
registered via ``registry.register_rep()`` / ``registry.register_index()``.
"""

from __future__ import annotations

import hashlib
import logging

from app.models.search import SearchResult
from app.services.registry import (
    IndexContext,
    RepContext,
    RepResult,
    SearchContext,
    registry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MD Representation Template
# ---------------------------------------------------------------------------


class MdRepTemplate:
    """Build canonical_md representation from Markdown source.

    For .md files the "transformation" is essentially a pass-through:
    canonical_md = source content.  This template also saves the raw
    source as ``source_original`` and produces the canonical_md rep.
    """

    name = "md_to_canonical"
    rep_type = "canonical_md"
    source_extensions = [".md"]
    entity_types: list[str] = []  # empty = all entity types

    async def build(self, ctx: RepContext) -> RepResult:
        """Transform MD source into canonical_md representation."""
        md_content = ctx.source_content.decode("utf-8", errors="replace")
        content_hash = hashlib.sha256(ctx.source_content).hexdigest()[:16]

        # Save source_original first
        ctx.storage.save_file(
            ctx.workspace_id, ctx.collection_id, ctx.entity_id,
            "source_original", ctx.source_content,
        )

        # For .md files, canonical_md = source content (no transformation)
        return RepResult(
            content=md_content.encode("utf-8"),
            rep_type="canonical_md",
            metadata={
                "transform": "parse",
                "input_content_hash": content_hash,
                "content_hash": content_hash,
                "modality": "text",
            },
        )


# ---------------------------------------------------------------------------
# Vector Index Template
# ---------------------------------------------------------------------------


class VectorIndexTemplate:
    """Index chunks using vector embeddings (semantic search).

    This is the default index strategy: embed chunk text, upsert to
    LanceDB, and support semantic / lexical / hybrid search.
    """

    name = "vector_index"
    index_type = "vector"

    async def build(self, ctx: IndexContext) -> None:
        """Upsert chunks with vectors into the index."""
        await ctx.index_service.upsert_chunks(
            ctx.workspace_id, ctx.collection_id, ctx.entity_id,
            ctx.chunks,
        )

    async def search(self, ctx: SearchContext) -> list[SearchResult]:
        """Search using the configured search_type."""
        search_type = ctx.params.get("search_type", "semantic")

        if search_type == "lexical":
            return await ctx.index_service.search_lexical(
                ctx.workspace_id, ctx.collection_id,
                ctx.query, top_k=ctx.top_k,
            )

        if search_type == "hybrid" and ctx.query_vector is not None:
            return await ctx.index_service.search_hybrid(
                ctx.workspace_id, ctx.collection_id,
                ctx.query, ctx.query_vector,
                top_k=ctx.top_k,
                rrf_k=ctx.params.get("rrf_k", 60),
                semantic_weight=ctx.params.get("semantic_weight", 0.7),
                lexical_weight=ctx.params.get("lexical_weight", 0.3),
            )

        # Default: semantic
        if ctx.query_vector is not None:
            return await ctx.index_service.search(
                ctx.workspace_id, ctx.collection_id,
                ctx.query_vector, top_k=ctx.top_k,
            )

        # No vector available — fall back to lexical
        return await ctx.index_service.search_lexical(
            ctx.workspace_id, ctx.collection_id,
            ctx.query, top_k=ctx.top_k,
        )


# ---------------------------------------------------------------------------
# Auto-registration helper
# ---------------------------------------------------------------------------


def register_builtin_templates() -> None:
    """Register all built-in templates into the global registry.

    Called once at application startup.
    """
    registry.register_rep(MdRepTemplate())
    registry.register_index(VectorIndexTemplate())
    logger.info("Built-in templates registered")
