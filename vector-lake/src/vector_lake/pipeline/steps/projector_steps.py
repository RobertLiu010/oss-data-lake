"""Built-in ProjectorStep implementations (§11).

v0.1: project_rag_api (RAG API 投影)
v0.2 stubs: project_wiki (Wiki 投影), project_dashboard, project_web
"""

from __future__ import annotations

import logging
from typing import Any

from vector_lake.pipeline.protocols import (
    RepStepContext,
    RepStepOutput,
)

logger = logging.getLogger(__name__)


class RagApiProjectorStep:
    """RAG API 投影 (§11.3): 将 Lake 内部数据投影为 RAG API 可消费的 JSON Evidence.

    这是 v0.1 唯一实现的 Projector。它不写回 Lake 内部，
    而是注册 HTTP 路由 /tools/* 供外部 RAG 应用调用。

    实际投影逻辑在 API 层 (vector_lake.api.routes.search) 中实现，
    此 Step 主要负责确保数据就绪 + 注册路由。
    """

    @property
    def step_id(self) -> str:
        return "project_rag_api"

    @property
    def name(self) -> str:
        return "RAG API 投影"

    @property
    def target(self) -> str:
        return "rag_api"

    @property
    def required_reps(self) -> list[str]:
        return ["canonical_md"]

    @property
    def output_reps(self) -> list[str]:
        return []  # Projector 不产出 Lake 内部 rep

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document", "table"]

    @property
    def modality(self) -> str:
        return "text"

    @property
    def optional_input_reps(self) -> list[str]:
        return ["ocr_text", "vlm_md", "summary"]

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """RAG API projection: verify data is ready for RAG consumption.

        ProjectorStep returns empty list (产出不写回 Lake).
        Actual RAG API serving is handled by the REST API layer.
        """
        logger.info(f"[project_rag_api] Verifying RAG readiness for entity={ctx.entity_id}")

        # Verify that at least one text rep is available
        available_text_reps = []
        for rep_type in ["canonical_md", "ocr_text", "vlm_md"]:
            if rep_type in ctx.upstream_outputs:
                available_text_reps.append(rep_type)

        if not available_text_reps:
            logger.warning(
                f"[project_rag_api] No text reps available for "
                f"entity={ctx.entity_id}, skipping projection"
            )
            return []

        logger.info(
            f"[project_rag_api] Entity={ctx.entity_id} ready with text_reps={available_text_reps}"
        )
        return []  # Projector 产出不写回 Lake

    def capabilities(self) -> dict[str, Any]:
        return {
            "requires_llm": False,
            "requires_gpu": False,
            "estimated_duration_ms": 100,
        }


class WikiProjectorStep:
    """Wiki 投影 (§11.3, §12): 将 Lake 数据投影为 Obsidian 兼容的 Wiki 文件.

    v0.2 stub. 详设见 PRD §12.
    """

    @property
    def step_id(self) -> str:
        return "project_wiki"

    @property
    def name(self) -> str:
        return "Wiki 投影"

    @property
    def target(self) -> str:
        return "wiki"

    @property
    def required_reps(self) -> list[str]:
        return ["canonical_md"]

    @property
    def output_reps(self) -> list[str]:
        return []

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document"]

    @property
    def modality(self) -> str:
        return "wiki"

    @property
    def optional_input_reps(self) -> list[str]:
        return ["wiki_md", "graph_json", "summary"]

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Wiki projection: write .md files to ~/wiki/ vault.

        TODO: implement per §12 design.
        1. Read canonical_md from upstream_outputs
        2. Optionally read wiki_md, graph_json, summary
        3. Render to Obsidian-compatible .md with frontmatter + wikilinks
        4. Atomic write to ~/wiki/entities/{slug}.md
        """
        raise NotImplementedError("WikiProjectorStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {
            "requires_llm": False,
            "requires_gpu": False,
            "estimated_duration_ms": 500,
        }


class DashboardProjectorStep:
    """Dashboard 投影 (§11.3): 指标/状态卡片. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "project_dashboard"

    @property
    def name(self) -> str:
        return "Dashboard 投影"

    @property
    def target(self) -> str:
        return "dashboard"

    @property
    def required_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return []

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document", "image", "audio", "table"]

    @property
    def modality(self) -> str:
        return "text"

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        raise NotImplementedError("DashboardProjectorStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"requires_llm": False, "requires_gpu": False, "estimated_duration_ms": 200}


class WebProjectorStep:
    """Web 投影 (§11.3): 视图模型. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "project_web"

    @property
    def name(self) -> str:
        return "Web 投影"

    @property
    def target(self) -> str:
        return "web"

    @property
    def required_reps(self) -> list[str]:
        return []

    @property
    def output_reps(self) -> list[str]:
        return []

    @property
    def output_stage(self) -> str:
        return "compile"

    @property
    def supported_entity_types(self) -> list[str]:
        return ["document", "image", "audio", "table"]

    @property
    def modality(self) -> str:
        return "text"

    @property
    def optional_input_reps(self) -> list[str]:
        return []

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        raise NotImplementedError("WebProjectorStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"requires_llm": False, "requires_gpu": False, "estimated_duration_ms": 200}


def register_builtin_projector_steps() -> None:
    """Register all built-in ProjectorSteps into ProjectorStepRegistry."""
    from vector_lake.pipeline.registry import ProjectorStepRegistry

    # v0.1
    ProjectorStepRegistry.register(RagApiProjectorStep())

    # v0.2 stubs
    ProjectorStepRegistry.register(WikiProjectorStep())
    ProjectorStepRegistry.register(DashboardProjectorStep())
    ProjectorStepRegistry.register(WebProjectorStep())

    logger.info(f"Registered {len(ProjectorStepRegistry.all_steps())} built-in ProjectorSteps")
