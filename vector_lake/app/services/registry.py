"""Representation and Index template registry.

Provides a plugin-style registry so that new representation builders and
index strategies can be registered at startup (or dynamically) and looked
up by name when processing entities.

Core concepts
-------------
- **RepTemplate**: describes how to transform raw source content into a
  *representation* (e.g. MD → canonical_md, PDF → text, Image → OCR text).
  Each template declares the file extensions it can handle and the
  ``rep_type`` string it produces.

- **IndexTemplate**: describes how to index chunks produced by a
  representation (e.g. vector search, FTS, hybrid RRF).  Each template
  declares the ``index_type`` string and provides ``build`` / ``search``
  hooks.

- **TemplateRegistry**: singleton that holds all registered templates and
  resolves the correct pipeline for a given file extension or entity type.

Usage
-----
    from app.services.registry import registry, RepTemplate, IndexTemplate

    # Register a new representation builder
    class PdfRepTemplate(RepTemplate):
        name = "pdf_to_text"
        rep_type = "canonical_text"
        source_extensions = [".pdf"]

        async def build(self, ctx: RepContext) -> RepResult:
            text = extract_pdf(ctx.source_content)
            return RepResult(content=text.encode(), metadata={})

    registry.register_rep(PdfRepTemplate())

    # Register a new index strategy
    class FtsOnlyIndex(IndexTemplate):
        name = "fts_only"
        index_type = "fts"

        async def build(self, ctx: IndexContext) -> None:
            ...

        async def search(self, ctx: SearchContext) -> list[SearchResult]:
            ...

    registry.register_index(FtsOnlyIndex())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.models.search import SearchResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context objects — passed to template methods so they have everything they need
# ---------------------------------------------------------------------------


@dataclass
class RepContext:
    """Input context for RepTemplate.build()."""

    workspace_id: str
    collection_id: str
    entity_id: str
    filename: str
    source_content: bytes  # raw file bytes
    # Shared storage reference so templates can save their output
    storage: Any  # StorageProtocol — use Any to avoid circular import
    settings: Any  # Settings


@dataclass
class RepResult:
    """Output of RepTemplate.build()."""

    content: bytes  # the representation content
    rep_type: str  # e.g. "canonical_md"
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional: additional rep files to save (rep_type → bytes)
    extra_reps: dict[str, bytes] = field(default_factory=dict)


@dataclass
class IndexContext:
    """Input context for IndexTemplate.build()."""

    workspace_id: str
    collection_id: str
    entity_id: str
    chunks: list[dict[str, Any]]  # [{chunk_index, text, embedding, metadata}]
    index_service: Any  # IndexService — use Any to avoid circular import
    settings: Any


@dataclass
class SearchContext:
    """Input context for IndexTemplate.search()."""

    workspace_id: str
    collection_id: str
    query: str
    index_service: Any  # IndexService
    settings: Any
    query_vector: list[float] | None = None
    top_k: int = 5
    # Template-specific params
    params: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Template protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class RepTemplate(Protocol):
    """Protocol for representation builder templates.

    Subclass and implement ``build()`` to create a new representation type.
    """

    name: str  # human-readable template name (unique)
    rep_type: str  # the rep_type this template produces
    source_extensions: list[str]  # file extensions this template handles (e.g. [".md"])
    # Optional: which entity types this template supports (empty = all)
    entity_types: list[str]

    async def build(self, ctx: RepContext) -> RepResult:
        """Transform source content into a representation.

        The implementation should:
        1. Parse / transform ``ctx.source_content``
        2. Return a RepResult with the transformed content and metadata
        """
        ...


@runtime_checkable
class IndexTemplate(Protocol):
    """Protocol for index strategy templates.

    Subclass and implement ``build()`` and ``search()`` to create a new
    index strategy.
    """

    name: str  # human-readable template name (unique)
    index_type: str  # e.g. "vector", "fts", "hybrid"

    async def build(self, ctx: IndexContext) -> None:
        """Build / update the index for the given chunks."""
        ...

    async def search(self, ctx: SearchContext) -> list[SearchResult]:
        """Search the index using the given query context."""
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TemplateRegistry:
    """Central registry for Rep and Index templates.

    Provides lookup by name, extension, and type so that the pipeline can
    dynamically resolve which templates to use for a given input.
    """

    def __init__(self) -> None:
        self._rep_templates: dict[str, RepTemplate] = {}
        self._index_templates: dict[str, IndexTemplate] = {}
        # Extension → list of rep template names (for fast lookup)
        self._extension_map: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_rep(self, template: RepTemplate) -> None:
        """Register a representation builder template."""
        if template.name in self._rep_templates:
            raise ValueError(f"RepTemplate '{template.name}' already registered")
        self._rep_templates[template.name] = template
        for ext in template.source_extensions:
            self._extension_map.setdefault(ext.lower(), []).append(template.name)
        logger.info(
            "Registered RepTemplate '%s' (rep_type=%s, extensions=%s)",
            template.name, template.rep_type, template.source_extensions,
        )

    def register_index(self, template: IndexTemplate) -> None:
        """Register an index strategy template."""
        if template.name in self._index_templates:
            raise ValueError(f"IndexTemplate '{template.name}' already registered")
        self._index_templates[template.name] = template
        logger.info(
            "Registered IndexTemplate '%s' (index_type=%s)",
            template.name, template.index_type,
        )

    def unregister_rep(self, name: str) -> None:
        """Remove a registered RepTemplate by name."""
        template = self._rep_templates.pop(name, None)
        if template is None:
            raise KeyError(f"RepTemplate '{name}' not found")
        for ext in template.source_extensions:
            names = self._extension_map.get(ext.lower(), [])
            if name in names:
                names.remove(name)
            if not names:
                self._extension_map.pop(ext.lower(), None)

    def unregister_index(self, name: str) -> None:
        """Remove a registered IndexTemplate by name."""
        if name not in self._index_templates:
            raise KeyError(f"IndexTemplate '{name}' not found")
        del self._index_templates[name]

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_rep_template(self, name: str) -> RepTemplate | None:
        """Get a RepTemplate by name."""
        return self._rep_templates.get(name)

    def get_index_template(self, name: str) -> IndexTemplate | None:
        """Get an IndexTemplate by name."""
        return self._index_templates.get(name)

    def find_rep_templates_for_extension(self, ext: str) -> list[RepTemplate]:
        """Find all RepTemplates that handle the given file extension."""
        names = self._extension_map.get(ext.lower(), [])
        return [self._rep_templates[n] for n in names if n in self._rep_templates]

    def find_rep_template_for_file(self, filename: str) -> RepTemplate | None:
        """Find the first RepTemplate that handles the given filename's extension."""
        ext = self._get_extension(filename)
        templates = self.find_rep_templates_for_extension(ext)
        return templates[0] if templates else None

    def list_rep_templates(self) -> list[dict[str, Any]]:
        """List all registered RepTemplates as dicts."""
        return [
            {
                "name": t.name,
                "rep_type": t.rep_type,
                "source_extensions": t.source_extensions,
                "entity_types": getattr(t, "entity_types", []),
            }
            for t in self._rep_templates.values()
        ]

    def list_index_templates(self) -> list[dict[str, Any]]:
        """List all registered IndexTemplates as dicts."""
        return [
            {
                "name": t.name,
                "index_type": t.index_type,
            }
            for t in self._index_templates.values()
        ]

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Extract the extension from a filename (lowercase, with dot)."""
        idx = filename.rfind(".")
        return filename[idx:].lower() if idx >= 0 else ""


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

registry = TemplateRegistry()
