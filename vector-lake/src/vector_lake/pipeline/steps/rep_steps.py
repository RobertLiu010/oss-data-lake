"""Built-in RepStep implementations (§6.6.3).

v0.1 steps: parse, render_page, ocr, transcribe, table_parse
v0.2 stubs: vlm, compile_mind_map, compile_graph_json, compile_summary, compile_wiki_md
"""

from __future__ import annotations

import logging
from typing import Any

from vector_lake.pipeline.protocols import (
    RepStepContext,
    RepStepOutput,
)

logger = logging.getLogger(__name__)


class ParseRepStep:
    """文档解析 (§6.6.3): raw → canonical_md + plain_text.

    Parses PDF/DOCX/HTML/etc into structured markdown and plain text.
    v0.1: Uses marker / docling / unstructured as backend.
    """

    @property
    def step_id(self) -> str:
        return "parse"

    @property
    def name(self) -> str:
        return "文档解析"

    @property
    def required_input_reps(self) -> list[str]:
        return ["raw"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["canonical_md", "plain_text"]

    @property
    def output_stage(self) -> str:
        return "extract"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "text"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Parse document into canonical markdown and plain text.

        TODO: integrate with marker/docling/unstructured for actual parsing.
        v0.1 skeleton: reads raw file, produces placeholder outputs.
        """
        logger.info(
            f"[parse] Processing entity={ctx.entity_id} content_hash={ctx.content_hash[:12]}..."
        )

        # TODO: actual parsing logic
        # raw_data = read from OSS via ctx
        # canonical_md = parse_document(raw_data)
        # plain_text = extract_text(canonical_md)

        canonical_md_content = b"# Placeholder: parsed content\n\nTODO: implement parsing"
        plain_text_content = b"Placeholder: plain text content. TODO: implement parsing"

        return [
            RepStepOutput(
                rep_type="canonical_md",
                stage="extract",
                files={"canonical.md": canonical_md_content},
                tags={
                    "rep_type": "canonical_md",
                    "pipeline_id": ctx.entity_id,
                    "transform": "parse",
                    "modality": "text",
                    "status": "ready",
                    "model_version": "marker-v1",
                    "entity_version": str(ctx.entity_version),
                },
            ),
            RepStepOutput(
                rep_type="plain_text",
                stage="extract",
                files={"plain_text.txt": plain_text_content},
                tags={
                    "rep_type": "plain_text",
                    "pipeline_id": ctx.entity_id,
                    "transform": "parse",
                    "modality": "text",
                    "status": "ready",
                    "model_version": "marker-v1",
                    "entity_version": str(ctx.entity_version),
                },
            ),
        ]

    def capabilities(self) -> dict[str, Any]:
        return {
            "requires_llm": False,
            "requires_gpu": False,
            "estimated_duration_ms": 5000,
        }


class RenderPageRepStep:
    """页面渲染 (§6.6.3): raw → page_image.

    Renders document pages to images (PNG).
    v0.1: Uses pdf2image / pymupdf as backend.
    """

    @property
    def step_id(self) -> str:
        return "render_page"

    @property
    def name(self) -> str:
        return "页面渲染"

    @property
    def required_input_reps(self) -> list[str]:
        return ["raw"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["page_image"]

    @property
    def output_stage(self) -> str:
        return "extract"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document", "image"]

    @property
    def modality(self) -> str:
        return "image"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Render document pages to images.

        TODO: integrate with pdf2image/pymupdf.
        """
        logger.info(f"[render_page] Processing entity={ctx.entity_id}")

        # TODO: actual rendering logic
        # raw_data = read from OSS
        # images = render_pages(raw_data)
        # For each page: save as page_{i}.png

        return [
            RepStepOutput(
                rep_type="page_image",
                stage="extract",
                files={"page_0.png": b"PLACEHOLDER_IMAGE_DATA"},
                tags={
                    "rep_type": "page_image",
                    "pipeline_id": ctx.entity_id,
                    "transform": "render_page",
                    "modality": "image",
                    "status": "ready",
                    "model_version": "pdf2image-v1",
                    "entity_version": str(ctx.entity_version),
                },
            ),
        ]

    def capabilities(self) -> dict[str, Any]:
        return {
            "requires_llm": False,
            "requires_gpu": False,
            "estimated_duration_ms": 3000,
        }


class OcrRepStep:
    """OCR 识别 (§6.6.3): page_image → ocr_text.

    Extracts text from page images using OCR.
    v0.1: Uses PaddleOCR / Tesseract / surya as backend.
    """

    @property
    def step_id(self) -> str:
        return "ocr"

    @property
    def name(self) -> str:
        return "OCR 识别"

    @property
    def required_input_reps(self) -> list[str]:
        return ["page_image"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["ocr_text"]

    @property
    def output_stage(self) -> str:
        return "recognize"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "text"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Extract text from page images via OCR.

        TODO: integrate with PaddleOCR/surya.
        """
        logger.info(f"[ocr] Processing entity={ctx.entity_id}")

        # TODO: actual OCR logic
        # page_images = ctx.upstream_outputs.get("page_image")
        # ocr_text = run_ocr(page_images)

        return [
            RepStepOutput(
                rep_type="ocr_text",
                stage="recognize",
                files={"ocr.md": b"# OCR Output\n\nTODO: implement OCR"},
                tags={
                    "rep_type": "ocr_text",
                    "pipeline_id": ctx.entity_id,
                    "transform": "ocr",
                    "modality": "text",
                    "status": "ready",
                    "model_version": "surya-v1",
                    "entity_version": str(ctx.entity_version),
                },
            ),
        ]

    def capabilities(self) -> dict[str, Any]:
        return {
            "requires_llm": False,
            "requires_gpu": True,
            "estimated_duration_ms": 8000,
        }


class TranscribeRepStep:
    """音频转写 (§6.6.3): raw → transcript + audio_segment.

    Transcribes audio to text and segments audio.
    v0.1: Uses Whisper / FunASR as backend.
    """

    @property
    def step_id(self) -> str:
        return "transcribe"

    @property
    def name(self) -> str:
        return "音频转写"

    @property
    def required_input_reps(self) -> list[str]:
        return ["raw"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["transcript", "audio_segment"]

    @property
    def output_stage(self) -> str:
        return "recognize"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["audio"]

    @property
    def modality(self) -> str:
        return "audio"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Transcribe audio to text and segment.

        TODO: integrate with Whisper/FunASR.
        """
        logger.info(f"[transcribe] Processing entity={ctx.entity_id}")

        return [
            RepStepOutput(
                rep_type="transcript",
                stage="recognize",
                files={"transcript.md": b"# Transcript\n\nTODO: implement transcription"},
                tags={
                    "rep_type": "transcript",
                    "pipeline_id": ctx.entity_id,
                    "transform": "transcribe",
                    "modality": "audio",
                    "status": "ready",
                    "model_version": "whisper-large-v3",
                    "entity_version": str(ctx.entity_version),
                },
            ),
            RepStepOutput(
                rep_type="audio_segment",
                stage="recognize",
                files={"segment_0.wav": b"PLACEHOLDER_AUDIO_DATA"},
                tags={
                    "rep_type": "audio_segment",
                    "pipeline_id": ctx.entity_id,
                    "transform": "transcribe",
                    "modality": "audio",
                    "status": "ready",
                    "model_version": "whisper-large-v3",
                    "entity_version": str(ctx.entity_version),
                },
            ),
        ]

    def capabilities(self) -> dict[str, Any]:
        return {
            "requires_llm": False,
            "requires_gpu": True,
            "estimated_duration_ms": 15000,
        }


class TableParseRepStep:
    """表格解析 (§6.6.3): raw → table_parquet + table_md + table_json.

    Parses structured table data from documents.
    v0.1: Uses camelot / tabula as backend.
    """

    @property
    def step_id(self) -> str:
        return "table_parse"

    @property
    def name(self) -> str:
        return "表格解析"

    @property
    def required_input_reps(self) -> list[str]:
        return ["raw"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["table_parquet", "table_md", "table_json"]

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["table"]

    @property
    def modality(self) -> str:
        return "table"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Parse tables from documents.

        TODO: integrate with camelot/tabula.
        """
        logger.info(f"[table_parse] Processing entity={ctx.entity_id}")

        return [
            RepStepOutput(
                rep_type="table_parquet",
                stage="compile",
                files={"table.parquet": b"PLACEHOLDER_PARQUET"},
                tags={
                    "rep_type": "table_parquet",
                    "pipeline_id": ctx.entity_id,
                    "transform": "table_parse",
                    "modality": "table",
                    "status": "ready",
                    "model_version": "camelot-v1",
                    "entity_version": str(ctx.entity_version),
                },
            ),
            RepStepOutput(
                rep_type="table_md",
                stage="compile",
                files={"table.md": b"| col1 | col2 |\n| --- | --- |\n| TODO | implement |"},
                tags={
                    "rep_type": "table_md",
                    "pipeline_id": ctx.entity_id,
                    "transform": "table_parse",
                    "modality": "table",
                    "status": "ready",
                    "model_version": "camelot-v1",
                    "entity_version": str(ctx.entity_version),
                },
            ),
            RepStepOutput(
                rep_type="table_json",
                stage="compile",
                files={"table.json": b'{"columns": [], "rows": []}'},
                tags={
                    "rep_type": "table_json",
                    "pipeline_id": ctx.entity_id,
                    "transform": "table_parse",
                    "modality": "table",
                    "status": "ready",
                    "model_version": "camelot-v1",
                    "entity_version": str(ctx.entity_version),
                },
            ),
        ]

    def capabilities(self) -> dict[str, Any]:
        return {
            "requires_llm": False,
            "requires_gpu": False,
            "estimated_duration_ms": 4000,
        }


# ── v0.2 Stubs ──────────────────────────────────────────


class VlmRepStep:
    """VLM 视觉 (§6.6.3): page_image → vlm_md. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "vlm"

    @property
    def name(self) -> str:
        return "VLM 视觉理解"

    @property
    def required_input_reps(self) -> list[str]:
        return ["page_image"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["vlm_md"]

    @property
    def output_stage(self) -> str:
        return "recognize"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "text"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        raise NotImplementedError("VlmRepStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"requires_llm": True, "requires_gpu": True, "estimated_duration_ms": 12000}


class CompileMindMapRepStep:
    """脑图编译 (§6.6.3): canonical_md → mind_map. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "compile_mind_map"

    @property
    def name(self) -> str:
        return "脑图编译"

    @property
    def required_input_reps(self) -> list[str]:
        return ["canonical_md"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["mind_map"]

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "text"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        raise NotImplementedError("CompileMindMapRepStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"requires_llm": True, "requires_gpu": False, "estimated_duration_ms": 6000}


class CompileGraphJsonRepStep:
    """关系图编译 (§6.6.3): canonical_md → graph_json. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "compile_graph_json"

    @property
    def name(self) -> str:
        return "关系图编译"

    @property
    def required_input_reps(self) -> list[str]:
        return ["canonical_md"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["graph_json"]

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "text"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        raise NotImplementedError("CompileGraphJsonRepStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"requires_llm": True, "requires_gpu": False, "estimated_duration_ms": 8000}


class CompileSummaryRepStep:
    """摘要编译 (§6.6.3): canonical_md → summary. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "compile_summary"

    @property
    def name(self) -> str:
        return "摘要编译"

    @property
    def required_input_reps(self) -> list[str]:
        return ["canonical_md"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["summary"]

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "text"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        raise NotImplementedError("CompileSummaryRepStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"requires_llm": True, "requires_gpu": False, "estimated_duration_ms": 5000}


class CompileWikiMdRepStep:
    """Wiki 编译 (§6.6.3): canonical_md → wiki_md. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "compile_wiki_md"

    @property
    def name(self) -> str:
        return "Wiki 编译"

    @property
    def required_input_reps(self) -> list[str]:
        return ["canonical_md"]

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return ["wiki_md"]

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "wiki"

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        raise NotImplementedError("CompileWikiMdRepStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"requires_llm": True, "requires_gpu": False, "estimated_duration_ms": 7000}


def register_builtin_rep_steps() -> None:
    """Register all built-in RepSteps into RepStepRegistry."""
    from vector_lake.pipeline.registry import RepStepRegistry

    # v0.1 steps
    RepStepRegistry.register(ParseRepStep())
    RepStepRegistry.register(RenderPageRepStep())
    RepStepRegistry.register(OcrRepStep())
    RepStepRegistry.register(TranscribeRepStep())
    RepStepRegistry.register(TableParseRepStep())

    # v0.2 stubs (registered but will raise NotImplementedError on execute)
    RepStepRegistry.register(VlmRepStep())
    RepStepRegistry.register(CompileMindMapRepStep())
    RepStepRegistry.register(CompileGraphJsonRepStep())
    RepStepRegistry.register(CompileSummaryRepStep())
    RepStepRegistry.register(CompileWikiMdRepStep())

    logger.info(f"Registered {len(RepStepRegistry.all_steps())} built-in RepSteps")
