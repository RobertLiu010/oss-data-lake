"""Representation and Index template registry with multi-step pipeline support.

Core concepts
-------------
- **RepStep**: a single transformation step (e.g. docx → pdf, pdf → png).
  Each step declares its ``input_format`` and ``output_format`` so the
  registry can build a DAG and resolve the shortest path from any source
  format to the target format (default: ``md``).

- **RepPipeline**: a resolved chain of RepSteps.  The pipeline executes
  each step in order, saving every intermediate product as a rep file.

- **RepTemplate**: (legacy) a single-step representation builder that
  maps file extensions to rep types.  Kept for backward compatibility.

- **IndexTemplate**: describes how to index chunks (vector, FTS, hybrid).

- **TemplateRegistry**: singleton that holds all registered steps /
  templates and resolves the correct pipeline for a given file.

Multi-step example
------------------
    # Register steps: docx → pdf → png → md
    registry.register_step(WordToPdfStep())
    registry.register_step(PdfToPngStep())
    registry.register_step(PngToMdStep())

    # Resolve pipeline for a .docx file
    pipeline = registry.resolve_pipeline("docx")  # → [WordToPdf, PdfToPng, PngToMd]

    # The pipeline will produce 3 intermediate reps:
    #   source_original  (the raw .docx bytes)
    #   rep_pdf          (output of WordToPdf)
    #   rep_png          (output of PdfToPng)
    #   canonical_md     (output of PngToMd — final, chunkable text)
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.models.search import SearchResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context objects
# ---------------------------------------------------------------------------


@dataclass
class RepContext:
    """Input context for RepTemplate.build()."""

    workspace_id: str
    collection_id: str
    entity_id: str
    filename: str
    source_content: bytes
    storage: Any
    settings: Any


@dataclass
class RepResult:
    """Output of RepTemplate.build()."""

    content: bytes
    rep_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    extra_reps: dict[str, bytes] = field(default_factory=dict)


@dataclass
class StepContext:
    """Input context for RepStep.transform()."""

    workspace_id: str
    collection_id: str
    entity_id: str
    # Content from previous step (or raw source for the first step)
    input_content: bytes
    input_format: str  # e.g. "docx", "pdf", "png"
    # Step index in the pipeline (0-based)
    step_index: int
    storage: Any
    settings: Any


@dataclass
class StepResult:
    """Output of RepStep.transform()."""

    content: bytes
    output_format: str  # e.g. "pdf", "png", "md"
    metadata: dict[str, Any] = field(default_factory=dict)
    # Optional: text extracted from this step's output for indexing.
    # If provided and the step has index_mode set, this text will be
    # chunked and indexed independently (even for non-text formats like PDF).
    indexable_text: str | None = None


@dataclass
class IndexContext:
    """Input context for IndexTemplate.build()."""

    workspace_id: str
    collection_id: str
    entity_id: str
    chunks: list[dict[str, Any]]
    index_service: Any
    settings: Any


@dataclass
class SearchContext:
    """Input context for IndexTemplate.search()."""

    workspace_id: str
    collection_id: str
    query: str
    index_service: Any
    settings: Any
    query_vector: list[float] | None = None
    top_k: int = 5
    params: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# RepStep — single transformation step in a multi-step pipeline
# ---------------------------------------------------------------------------


@runtime_checkable
class RepStep(Protocol):
    """Protocol for a single representation transformation step.

    Each step declares its ``input_format`` and ``output_format``.
    The registry builds a DAG from all registered steps and resolves
    the shortest path from source to target format.

    **Per-step indexing**: a step can declare ``index_mode`` to have its
    output indexed independently.  Supported modes:

    - ``None``   — no indexing (default, for pure intermediate steps)
    - ``"text"`` — chunk + embed + vector index (standard text flow)
    - ``"lexical"`` — chunk + FTS index only (no embeddings)
    - ``"vision"`` — image embedding + vector index (future)

    When ``index_mode`` is set, the step should also provide
    ``indexable_text`` in its StepResult (or the pipeline will try
    to decode ``content`` as UTF-8 text).

    Example steps:
        - WordToPdf:  input_format="docx", output_format="pdf",
                      index_mode="text"  (index extracted PDF text)
        - PdfToPng:   input_format="pdf",  output_format="png",
                      index_mode=None  (no indexing of images)
        - PngToMd:    input_format="png",  output_format="md",
                      index_mode="text"  (index OCR text)
        - MdPassThru: input_format="md",   output_format="md",
                      index_mode="text"  (index markdown text)
    """

    name: str  # unique step name (e.g. "word_to_pdf")
    input_format: str  # source format (e.g. "docx")
    output_format: str  # target format (e.g. "pdf")
    index_mode: str | None  # None, "text", "lexical", "vision"

    async def transform(self, ctx: StepContext) -> StepResult:
        """Transform input content to output format."""
        ...


# ---------------------------------------------------------------------------
# RepTemplate (legacy single-step) and IndexTemplate protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class RepTemplate(Protocol):
    """Protocol for legacy single-step representation builders."""

    name: str
    rep_type: str
    source_extensions: list[str]
    entity_types: list[str]

    async def build(self, ctx: RepContext) -> RepResult:
        ...


@runtime_checkable
class IndexTemplate(Protocol):
    """Protocol for index strategy templates."""

    name: str
    index_type: str

    async def build(self, ctx: IndexContext) -> None:
        ...

    async def search(self, ctx: SearchContext) -> list[SearchResult]:
        ...


# ---------------------------------------------------------------------------
# RepPipeline — resolved chain of steps
# ---------------------------------------------------------------------------


@dataclass
class RepPipeline:
    """A resolved chain of RepSteps from source to target format.

    Created by ``TemplateRegistry.resolve_pipeline()``.
    """

    steps: list[RepStep]
    source_format: str
    target_format: str

    @property
    def step_names(self) -> list[str]:
        return [s.name for s in self.steps]

    def describe(self) -> str:
        """Human-readable description of the pipeline."""
        formats = [self.source_format]
        for step in self.steps:
            formats.append(step.output_format)
        return " → ".join(formats) + f"  (steps: {', '.join(self.step_names)})"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Default target format — the format that can be chunked into text
DEFAULT_TARGET_FORMAT = "md"


class TemplateRegistry:
    """Central registry for RepSteps, RepTemplates, and IndexTemplates.

    Supports both:
    - **Multi-step pipelines** via RepStep registration + DAG resolution
    - **Legacy single-step** via RepTemplate registration + extension lookup
    """

    def __init__(self) -> None:
        # Multi-step pipeline support
        self._steps: dict[str, RepStep] = {}
        # DAG edges: input_format → [(output_format, step_name)]
        self._dag: dict[str, list[tuple[str, str]]] = {}

        # Legacy single-step support
        self._rep_templates: dict[str, RepTemplate] = {}
        self._extension_map: dict[str, list[str]] = {}

        # Index templates
        self._index_templates: dict[str, IndexTemplate] = {}

        # Extension → format mapping (e.g. ".docx" → "docx")
        self._extension_format_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Step registration (multi-step pipeline)
    # ------------------------------------------------------------------

    def register_step(self, step: RepStep) -> None:
        """Register a RepStep for multi-step pipeline resolution."""
        if step.name in self._steps:
            raise ValueError(f"RepStep '{step.name}' already registered")
        self._steps[step.name] = step
        self._dag.setdefault(step.input_format, []).append(
            (step.output_format, step.name)
        )
        logger.info(
            "Registered RepStep '%s': %s → %s",
            step.name, step.input_format, step.output_format,
        )

    def unregister_step(self, name: str) -> None:
        """Remove a registered RepStep by name."""
        step = self._steps.pop(name, None)
        if step is None:
            raise KeyError(f"RepStep '{name}' not found")
        # Remove from DAG
        edges = self._dag.get(step.input_format, [])
        self._dag[step.input_format] = [
            (fmt, sname) for fmt, sname in edges if sname != name
        ]
        if not self._dag[step.input_format]:
            self._dag.pop(step.input_format, None)

    def get_step(self, name: str) -> RepStep | None:
        """Get a RepStep by name."""
        return self._steps.get(name)

    def list_steps(self) -> list[dict[str, Any]]:
        """List all registered RepSteps as dicts."""
        return [
            {
                "name": s.name,
                "input_format": s.input_format,
                "output_format": s.output_format,
                "index_mode": getattr(s, "index_mode", None),
            }
            for s in self._steps.values()
        ]

    # ------------------------------------------------------------------
    # Extension → format mapping
    # ------------------------------------------------------------------

    def register_extension_format(self, extension: str, format_name: str) -> None:
        """Map a file extension to a format name.

        Example: register_extension_format(".docx", "docx")
        """
        self._extension_format_map[extension.lower()] = format_name
        logger.debug("Mapped extension %s → format %s", extension, format_name)

    def get_format_for_extension(self, extension: str) -> str | None:
        """Get the format name for a file extension."""
        return self._extension_format_map.get(extension.lower())

    # ------------------------------------------------------------------
    # DAG resolution — find shortest path from source to target format
    # ------------------------------------------------------------------

    def resolve_pipeline(
        self,
        source_format: str,
        target_format: str = DEFAULT_TARGET_FORMAT,
    ) -> RepPipeline:
        """Resolve the shortest path from source_format to target_format.

        Uses BFS to find the shortest chain of RepSteps.
        Raises ValueError if no path exists.
        """
        if source_format == target_format:
            # Identity pipeline — no steps needed
            return RepPipeline(
                steps=[], source_format=source_format, target_format=target_format,
            )

        # BFS
        queue: deque[tuple[str, list[RepStep]]] = deque()
        queue.append((source_format, []))
        visited: set[str] = {source_format}

        while queue:
            current_format, path = queue.popleft()
            edges = self._dag.get(current_format, [])
            for output_format, step_name in edges:
                step = self._steps[step_name]
                new_path = path + [step]
                if output_format == target_format:
                    return RepPipeline(
                        steps=new_path,
                        source_format=source_format,
                        target_format=target_format,
                    )
                if output_format not in visited:
                    visited.add(output_format)
                    queue.append((output_format, new_path))

        raise ValueError(
            f"No pipeline path from '{source_format}' to '{target_format}'. "
            f"Registered formats reachable from '{source_format}': "
            f"{self._reachable_formats(source_format)}"
        )

    def resolve_pipeline_for_file(
        self,
        filename: str,
        target_format: str = DEFAULT_TARGET_FORMAT,
    ) -> RepPipeline:
        """Resolve a pipeline for a filename by looking up its extension format."""
        ext = self._get_extension(filename)
        source_format = self.get_format_for_extension(ext)
        if source_format is None:
            # Fallback: try stripping the dot from extension
            source_format = ext.lstrip(".") if ext else None
        if source_format is None:
            raise ValueError(
                f"Cannot determine format for file '{filename}'. "
                f"Register a format mapping with register_extension_format()."
            )
        return self.resolve_pipeline(source_format, target_format)

    def _reachable_formats(self, source_format: str) -> list[str]:
        """Return all formats reachable from source_format via BFS."""
        visited: set[str] = {source_format}
        queue: deque[str] = deque([source_format])
        while queue:
            current = queue.popleft()
            for output_format, _ in self._dag.get(current, []):
                if output_format not in visited:
                    visited.add(output_format)
                    queue.append(output_format)
        return sorted(visited - {source_format})

    # ------------------------------------------------------------------
    # Legacy RepTemplate registration
    # ------------------------------------------------------------------

    def register_rep(self, template: RepTemplate) -> None:
        """Register a representation builder template (legacy)."""
        if template.name in self._rep_templates:
            raise ValueError(f"RepTemplate '{template.name}' already registered")
        self._rep_templates[template.name] = template
        for ext in template.source_extensions:
            self._extension_map.setdefault(ext.lower(), []).append(template.name)
        logger.info(
            "Registered RepTemplate '%s' (rep_type=%s, extensions=%s)",
            template.name, template.rep_type, template.source_extensions,
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

    def get_rep_template(self, name: str) -> RepTemplate | None:
        """Get a RepTemplate by name."""
        return self._rep_templates.get(name)

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

    # ------------------------------------------------------------------
    # IndexTemplate registration
    # ------------------------------------------------------------------

    def register_index(self, template: IndexTemplate) -> None:
        """Register an index strategy template."""
        if template.name in self._index_templates:
            raise ValueError(f"IndexTemplate '{template.name}' already registered")
        self._index_templates[template.name] = template
        logger.info(
            "Registered IndexTemplate '%s' (index_type=%s)",
            template.name, template.index_type,
        )

    def unregister_index(self, name: str) -> None:
        """Remove a registered IndexTemplate by name."""
        if name not in self._index_templates:
            raise KeyError(f"IndexTemplate '{name}' not found")
        del self._index_templates[name]

    def get_index_template(self, name: str) -> IndexTemplate | None:
        """Get an IndexTemplate by name."""
        return self._index_templates.get(name)

    def list_index_templates(self) -> list[dict[str, Any]]:
        """List all registered IndexTemplates as dicts."""
        return [
            {
                "name": t.name,
                "index_type": t.index_type,
            }
            for t in self._index_templates.values()
        ]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Extract the extension from a filename (lowercase, with dot)."""
        idx = filename.rfind(".")
        return filename[idx:].lower() if idx >= 0 else ""


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

registry = TemplateRegistry()
