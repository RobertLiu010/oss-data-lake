"""Tests for the multi-step RepStep pipeline system.

Covers:
- Step registration / unregistration on TemplateRegistry
- Pipeline resolution (identity, single-step, multi-step, no-path)
- Extension → format mapping
- _reachable_formats helper
- RepPipeline.describe()
- PipelineService._execute_step_pipeline (md passthru, multi-step with mock steps)
- list_steps and register_builtin_templates
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.pipeline import PipelineService
from app.services.registry import (
    RepPipeline,
    StepContext,
    StepResult,
    TemplateRegistry,
)
from app.services.templates import (
    MdPassThruStep,
    PdfToPngStep,
    PngToMdStep,
    WordToPdfStep,
    register_builtin_templates,
)

# ---------------------------------------------------------------------------
# Helper steps for multi-step pipeline tests
# ---------------------------------------------------------------------------


class UpperStep:
    """Test step: lower → upper (transforms text to uppercase)."""

    name = "upper_step"
    input_format = "lower"
    output_format = "upper"

    async def transform(self, ctx: StepContext) -> StepResult:
        text = ctx.input_content.decode("utf-8")
        return StepResult(
            content=text.upper().encode("utf-8"),
            output_format="upper",
            metadata={"transform": "uppercase", "step": self.name},
        )


class LowerStep:
    """Test step: upper → md (transforms text to lowercase)."""

    name = "lower_step"
    input_format = "upper"
    output_format = "md"

    async def transform(self, ctx: StepContext) -> StepResult:
        text = ctx.input_content.decode("utf-8")
        return StepResult(
            content=text.lower().encode("utf-8"),
            output_format="md",
            metadata={"transform": "lowercase", "step": self.name},
        )


# ---------------------------------------------------------------------------
# 1. test_register_step
# ---------------------------------------------------------------------------


def test_register_step():
    """Register a custom step and verify it can be looked up."""
    reg = TemplateRegistry()
    step = UpperStep()
    reg.register_step(step)

    found = reg.get_step("upper_step")
    assert found is step
    assert found.name == "upper_step"
    assert found.input_format == "lower"
    assert found.output_format == "upper"


# ---------------------------------------------------------------------------
# 2. test_register_step_duplicate
# ---------------------------------------------------------------------------


def test_register_step_duplicate():
    """Registering a step with the same name twice raises ValueError."""
    reg = TemplateRegistry()
    reg.register_step(UpperStep())

    with pytest.raises(ValueError, match="already registered"):
        reg.register_step(UpperStep())


# ---------------------------------------------------------------------------
# 3. test_unregister_step
# ---------------------------------------------------------------------------


def test_unregister_step():
    """Unregister a step and verify it is gone."""
    reg = TemplateRegistry()
    reg.register_step(UpperStep())
    reg.unregister_step("upper_step")

    assert reg.get_step("upper_step") is None


# ---------------------------------------------------------------------------
# 4. test_unregister_step_not_found
# ---------------------------------------------------------------------------


def test_unregister_step_not_found():
    """Unregistering a non-existent step raises KeyError."""
    reg = TemplateRegistry()

    with pytest.raises(KeyError, match="not found"):
        reg.unregister_step("nonexistent")


# ---------------------------------------------------------------------------
# 5. test_resolve_pipeline_identity
# ---------------------------------------------------------------------------


def test_resolve_pipeline_identity():
    """md → md returns an empty pipeline (identity)."""
    reg = TemplateRegistry()
    pipeline = reg.resolve_pipeline("md", "md")

    assert pipeline.steps == []
    assert pipeline.source_format == "md"
    assert pipeline.target_format == "md"
    assert pipeline.step_names == []


# ---------------------------------------------------------------------------
# 6. test_resolve_pipeline_single_step
# ---------------------------------------------------------------------------


def test_resolve_pipeline_single_step():
    """png → md resolves via PngToMdStep."""
    reg = TemplateRegistry()
    reg.register_step(PngToMdStep())

    pipeline = reg.resolve_pipeline("png", "md")

    assert len(pipeline.steps) == 1
    assert pipeline.steps[0].name == "png_to_md"
    assert pipeline.source_format == "png"
    assert pipeline.target_format == "md"
    assert pipeline.step_names == ["png_to_md"]


# ---------------------------------------------------------------------------
# 7. test_resolve_pipeline_multi_step
# ---------------------------------------------------------------------------


def test_resolve_pipeline_multi_step():
    """docx → pdf → png → md resolves via 3 steps."""
    reg = TemplateRegistry()
    reg.register_step(WordToPdfStep())
    reg.register_step(PdfToPngStep())
    reg.register_step(PngToMdStep())

    pipeline = reg.resolve_pipeline("docx", "md")

    assert len(pipeline.steps) == 3
    assert pipeline.step_names == ["word_to_pdf", "pdf_to_png", "png_to_md"]
    assert pipeline.source_format == "docx"
    assert pipeline.target_format == "md"


# ---------------------------------------------------------------------------
# 8. test_resolve_pipeline_no_path
# ---------------------------------------------------------------------------


def test_resolve_pipeline_no_path():
    """No path from source to target raises ValueError."""
    reg = TemplateRegistry()
    # Only register a step for png → md, nothing reaches from docx
    reg.register_step(PngToMdStep())

    with pytest.raises(ValueError, match="No pipeline path"):
        reg.resolve_pipeline("docx", "md")


# ---------------------------------------------------------------------------
# 9. test_resolve_pipeline_for_file
# ---------------------------------------------------------------------------


def test_resolve_pipeline_for_file():
    """Resolve a pipeline by filename using extension mapping."""
    reg = TemplateRegistry()
    reg.register_extension_format(".docx", "docx")
    reg.register_step(WordToPdfStep())
    reg.register_step(PdfToPngStep())
    reg.register_step(PngToMdStep())

    pipeline = reg.resolve_pipeline_for_file("report.docx")

    assert len(pipeline.steps) == 3
    assert pipeline.step_names == ["word_to_pdf", "pdf_to_png", "png_to_md"]


# ---------------------------------------------------------------------------
# 10. test_extension_format_mapping
# ---------------------------------------------------------------------------


def test_extension_format_mapping():
    """Register and lookup extension → format mapping."""
    reg = TemplateRegistry()
    reg.register_extension_format(".docx", "docx")
    reg.register_extension_format(".PDF", "pdf")

    assert reg.get_format_for_extension(".docx") == "docx"
    assert reg.get_format_for_extension(".pdf") == "pdf"  # case-insensitive
    assert reg.get_format_for_extension(".PDF") == "pdf"
    assert reg.get_format_for_extension(".xyz") is None


# ---------------------------------------------------------------------------
# 11. test_reachable_formats
# ---------------------------------------------------------------------------


def test_reachable_formats():
    """_reachable_formats returns all formats reachable from a source."""
    reg = TemplateRegistry()
    reg.register_step(WordToPdfStep())  # docx → pdf
    reg.register_step(PdfToPngStep())  # pdf → png
    reg.register_step(PngToMdStep())  # png → md

    reachable = reg._reachable_formats("docx")
    assert reachable == ["md", "pdf", "png"]

    # From pdf, only png and md are reachable
    reachable_pdf = reg._reachable_formats("pdf")
    assert reachable_pdf == ["md", "png"]

    # From md, nothing is reachable (no outgoing edges)
    reachable_md = reg._reachable_formats("md")
    assert reachable_md == []


# ---------------------------------------------------------------------------
# 12. test_rep_pipeline_describe
# ---------------------------------------------------------------------------


def test_rep_pipeline_describe():
    """RepPipeline.describe() returns a human-readable description."""
    reg = TemplateRegistry()
    reg.register_step(WordToPdfStep())
    reg.register_step(PdfToPngStep())
    reg.register_step(PngToMdStep())

    pipeline = reg.resolve_pipeline("docx", "md")
    description = pipeline.describe()

    assert "docx" in description
    assert "pdf" in description
    assert "png" in description
    assert "md" in description
    assert "word_to_pdf" in description
    assert "pdf_to_png" in description
    assert "png_to_md" in description
    assert "→" in description

    # Identity pipeline
    identity = RepPipeline(steps=[], source_format="md", target_format="md")
    assert identity.describe() == "md  (steps: )"


# ---------------------------------------------------------------------------
# 13. test_execute_step_pipeline_md_passthru
# ---------------------------------------------------------------------------


async def test_execute_step_pipeline_md_passthru():
    """Execute md passthru pipeline with PipelineService."""
    reg = TemplateRegistry()
    reg.register_step(MdPassThruStep())
    reg.register_extension_format(".md", "md")

    mock_storage = MagicMock()
    mock_chunking = AsyncMock()
    mock_embedding = AsyncMock()
    mock_index = AsyncMock()
    mock_settings = MagicMock()

    pipeline_svc = PipelineService(
        storage=mock_storage,
        chunking=mock_chunking,
        embedding=mock_embedding,
        index=mock_index,
        settings=mock_settings,
        template_registry=reg,
    )

    md_content = b"# Hello\n\nWorld"
    pipeline = reg.resolve_pipeline("md", "md")

    canonical_text, metadata = await pipeline_svc._execute_step_pipeline(
        workspace_id="ws-1",
        collection_id="col-1",
        entity_id="ent-1",
        source_content=md_content,
        pipeline=pipeline,
    )

    assert canonical_text == md_content.decode("utf-8")
    assert metadata["transform"] == "passthru"
    # Identity pipeline saves canonical_md
    mock_storage.save_file.assert_called_once_with(
        "ws-1", "col-1", "ent-1", "canonical_md", md_content,
    )


# ---------------------------------------------------------------------------
# 14. test_execute_step_pipeline_multi_step
# ---------------------------------------------------------------------------


async def test_execute_step_pipeline_multi_step():
    """Execute a 2-step pipeline with mock UpperStep and LowerStep."""
    reg = TemplateRegistry()
    reg.register_step(UpperStep())  # lower → upper
    reg.register_step(LowerStep())  # upper → md
    reg.register_extension_format(".low", "lower")

    mock_storage = MagicMock()
    mock_chunking = AsyncMock()
    mock_embedding = AsyncMock()
    mock_index = AsyncMock()
    mock_settings = MagicMock()

    pipeline_svc = PipelineService(
        storage=mock_storage,
        chunking=mock_chunking,
        embedding=mock_embedding,
        index=mock_index,
        settings=mock_settings,
        template_registry=reg,
    )

    source_content = b"hello world"
    pipeline = reg.resolve_pipeline("lower", "md")

    canonical_text, metadata = await pipeline_svc._execute_step_pipeline(
        workspace_id="ws-2",
        collection_id="col-2",
        entity_id="ent-2",
        source_content=source_content,
        pipeline=pipeline,
    )

    # lower → upper → lower(md): "hello world" → "HELLO WORLD" → "hello world"
    assert canonical_text == "hello world"
    assert len(pipeline.steps) == 2
    assert pipeline.step_names == ["upper_step", "lower_step"]

    # Verify storage.save_file calls:
    # 1) Step 0 (intermediate): rep_upper with "HELLO WORLD"
    # 2) Step 1 (final): canonical_md with "hello world"
    save_calls = mock_storage.save_file.call_args_list
    assert len(save_calls) == 2

    # Intermediate step
    assert save_calls[0][0] == ("ws-2", "col-2", "ent-2", "rep_upper", b"HELLO WORLD")

    # Final step
    assert save_calls[1][0] == ("ws-2", "col-2", "ent-2", "canonical_md", b"hello world")

    # Metadata should include pipeline info
    assert metadata["pipeline_steps"] == ["upper_step", "lower_step"]
    assert len(metadata["intermediate_reps"]) == 2
    assert metadata["content_hash"] is not None
    assert metadata["modality"] == "text"


# ---------------------------------------------------------------------------
# 15. test_list_steps
# ---------------------------------------------------------------------------


def test_list_steps():
    """list_steps returns all registered steps as dicts."""
    reg = TemplateRegistry()
    reg.register_step(UpperStep())
    reg.register_step(LowerStep())

    steps = reg.list_steps()
    assert len(steps) == 2

    names = {s["name"] for s in steps}
    assert names == {"upper_step", "lower_step"}

    # Verify dict structure
    upper_entry = next(s for s in steps if s["name"] == "upper_step")
    assert upper_entry["input_format"] == "lower"
    assert upper_entry["output_format"] == "upper"


# ---------------------------------------------------------------------------
# 16. test_builtin_templates_register_steps
# ---------------------------------------------------------------------------


def test_builtin_templates_register_steps():
    """register_builtin_templates registers all steps into the global registry."""
    from app.services.registry import registry

    # Clear step-related state in the global registry for a clean test
    registry._steps.clear()
    registry._dag.clear()
    registry._extension_format_map.clear()
    registry._rep_templates.clear()
    registry._extension_map.clear()
    registry._index_templates.clear()

    register_builtin_templates()

    # Verify all 4 steps are registered
    step_names = {s["name"] for s in registry.list_steps()}
    assert step_names == {"md_passthru", "word_to_pdf", "pdf_to_png", "png_to_md"}

    # Verify individual steps
    md_step = registry.get_step("md_passthru")
    assert md_step is not None
    assert md_step.input_format == "md"
    assert md_step.output_format == "md"

    word_step = registry.get_step("word_to_pdf")
    assert word_step is not None
    assert word_step.input_format == "docx"
    assert word_step.output_format == "pdf"

    pdf_step = registry.get_step("pdf_to_png")
    assert pdf_step is not None
    assert pdf_step.input_format == "pdf"
    assert pdf_step.output_format == "png"

    png_step = registry.get_step("png_to_md")
    assert png_step is not None
    assert png_step.input_format == "png"
    assert png_step.output_format == "md"

    # Verify extension format mappings
    assert registry.get_format_for_extension(".md") == "md"
    assert registry.get_format_for_extension(".docx") == "docx"
    assert registry.get_format_for_extension(".pdf") == "pdf"
    assert registry.get_format_for_extension(".png") == "png"

    # Verify pipeline resolution works end-to-end
    pipeline = registry.resolve_pipeline("docx", "md")
    assert pipeline.step_names == ["word_to_pdf", "pdf_to_png", "png_to_md"]
