"""Built-in templates and steps for the template registry.

Provides:
- **MdPassThru step**: md → md identity step (no transformation needed)
- **MdRepTemplate** (legacy): backward-compat single-step MD builder
- **VectorIndexTemplate**: default vector index strategy
- **Example step skeletons**: WordToPdf, PdfToPng, PngToMd (raise
  NotImplementedError until a real converter is plugged in)

Extension → format mappings are also registered here so that
``registry.resolve_pipeline_for_file("report.docx")`` works.
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
    StepContext,
    StepResult,
    registry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RepSteps — multi-step pipeline building blocks
# ---------------------------------------------------------------------------


class MdPassThruStep:
    """Identity step: md → md.

    When the source format is already ``md``, no transformation is needed.
    This step simply passes the content through unchanged.
    """

    name = "md_passthru"
    input_format = "md"
    output_format = "md"
    index_mode = "text"  # index the markdown text

    async def transform(self, ctx: StepContext) -> StepResult:
        """Pass through MD content unchanged."""
        text = ctx.input_content.decode("utf-8", errors="replace")
        return StepResult(
            content=ctx.input_content,
            output_format="md",
            metadata={
                "transform": "passthru",
                "step": self.name,
                "step_index": ctx.step_index,
            },
            indexable_text=text,
        )


class WordToPdfStep:
    """Convert Word (.docx) to PDF.

    **Requires an external converter** (e.g. LibreOffice headless).
    Raises NotImplementedError until a converter backend is configured.

    index_mode="text": when a real converter is plugged in, the step
    should extract text from the DOCX and provide it as indexable_text
    so the document is searchable even at the PDF stage.
    """

    name = "word_to_pdf"
    input_format = "docx"
    output_format = "pdf"
    index_mode = "text"  # index extracted text from DOCX

    async def transform(self, ctx: StepContext) -> StepResult:
        """Convert DOCX bytes to PDF bytes.

        Override this step or replace it with a real implementation
        that calls LibreOffice / Gotenberg / etc.
        """
        raise NotImplementedError(
            "WordToPdfStep: no converter backend configured. "
            "Install LibreOffice or register a custom step."
        )


class PdfToPngStep:
    """Convert PDF to PNG images.

    **Requires an external converter** (e.g. pdf2image / Poppler).
    Raises NotImplementedError until a converter backend is configured.

    index_mode=None: PNG images are not text-searchable, so no
    per-step indexing.  The text will be indexed at the final MD step.
    """

    name = "pdf_to_png"
    input_format = "pdf"
    output_format = "png"
    index_mode = None  # images are not text-searchable

    async def transform(self, ctx: StepContext) -> StepResult:
        """Convert PDF bytes to PNG bytes.

        Override this step or replace it with a real implementation
        that calls pdf2image / Poppler / etc.
        """
        raise NotImplementedError(
            "PdfToPngStep: no converter backend configured. "
            "Install poppler-utils or register a custom step."
        )


class PngToMdStep:
    """Convert PNG image to Markdown via OCR.

    **Requires an external OCR engine** (e.g. Tesseract, PaddleOCR).
    Raises NotImplementedError until an OCR backend is configured.

    index_mode="text": the OCR text will be indexed as soon as
    this step completes.
    """

    name = "png_to_md"
    input_format = "png"
    output_format = "md"
    index_mode = "text"  # index OCR text

    async def transform(self, ctx: StepContext) -> StepResult:
        """Convert PNG bytes to Markdown text via OCR.

        Override this step or replace it with a real implementation
        that calls Tesseract / PaddleOCR / etc.
        """
        raise NotImplementedError(
            "PngToMdStep: no OCR backend configured. "
            "Install Tesseract or register a custom step."
        )


# ---------------------------------------------------------------------------
# Legacy RepTemplate — backward compat
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
    entity_types: list[str] = []

    async def build(self, ctx: RepContext) -> RepResult:
        """Transform MD source into canonical_md representation."""
        md_content = ctx.source_content.decode("utf-8", errors="replace")
        content_hash = hashlib.sha256(ctx.source_content).hexdigest()[:16]

        ctx.storage.save_file(
            ctx.workspace_id, ctx.collection_id, ctx.entity_id,
            "source_original", ctx.source_content,
        )

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
# Index Templates
# ---------------------------------------------------------------------------


class VectorIndexTemplate:
    """Index chunks using vector embeddings (semantic search)."""

    name = "vector_index"
    index_type = "vector"

    async def build(self, ctx: IndexContext) -> None:
        """Upsert chunks with vectors into the index."""
        rep_name = ctx.chunks[0].get("rep_name", "canonical_md") if ctx.chunks else "canonical_md"
        await ctx.index_service.upsert_chunks(
            ctx.workspace_id, ctx.collection_id, ctx.entity_id,
            ctx.chunks,
            rep_name=rep_name,
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

        if ctx.query_vector is not None:
            return await ctx.index_service.search(
                ctx.workspace_id, ctx.collection_id,
                ctx.query_vector, top_k=ctx.top_k,
            )

        return await ctx.index_service.search_lexical(
            ctx.workspace_id, ctx.collection_id,
            ctx.query, top_k=ctx.top_k,
        )


# ---------------------------------------------------------------------------
# Auto-registration
# ---------------------------------------------------------------------------

# Extension → format mapping for common file types
_EXTENSION_FORMAT_MAP: dict[str, str] = {
    ".md": "md",
    ".markdown": "md",
    ".docx": "docx",
    ".doc": "docx",
    ".pdf": "pdf",
    ".png": "png",
    ".jpg": "png",
    ".jpeg": "png",
    ".tiff": "png",
    ".bmp": "png",
    ".txt": "md",  # plain text treated as md
    ".html": "md",  # HTML treated as md (after stripping tags)
}


def register_builtin_templates() -> None:
    """Register all built-in steps, templates, and mappings.

    Called once at application startup.
    """
    # Register extension → format mappings
    for ext, fmt in _EXTENSION_FORMAT_MAP.items():
        registry.register_extension_format(ext, fmt)

    # Register RepSteps (multi-step pipeline)
    registry.register_step(MdPassThruStep())
    # Skeleton steps — raise NotImplementedError until backend is configured
    registry.register_step(WordToPdfStep())
    registry.register_step(PdfToPngStep())
    registry.register_step(PngToMdStep())

    # Register legacy RepTemplate (backward compat)
    registry.register_rep(MdRepTemplate())

    # Register IndexTemplate
    registry.register_index(VectorIndexTemplate())

    logger.info("Built-in templates and steps registered")
