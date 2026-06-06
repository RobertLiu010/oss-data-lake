"""Built-in IndexStep implementations (§6.7.3).

v0.1 steps: chunk_and_embed_text, build_vector_index, build_fts_index
v0.2 stubs: chunk_and_embed_image, chunk_and_embed_audio, build_graph_index,
            chunk_and_embed_table
"""

from __future__ import annotations

import logging
from typing import Any

from vector_lake.pipeline.protocols import IndexStepContext

logger = logging.getLogger(__name__)


class ChunkAndEmbedTextIndexStep:
    """文本切片+嵌入 (§6.7.3): canonical_md/ocr_text/vlm_md → LanceDB chunks.

    Splits text into chunks, generates embeddings, writes to LanceDB.
    v0.1: Uses Jina V5 / BGE as embedding backend.
    """

    @property
    def step_id(self) -> str:
        return "chunk_and_embed_text"

    @property
    def name(self) -> str:
        return "文本切片+嵌入"

    @property
    def index_type(self) -> str:
        return "semantic"

    @property
    def required_reps(self) -> list[str]:
        return []  # Any one of: canonical_md, ocr_text, vlm_md

    @property
    def optional_reps(self) -> list[str]:
        return ["canonical_md", "ocr_text", "vlm_md"]

    @property
    def supported_modalities(self) -> list[str]:
        return ["text"]

    def execute(self, ctx: IndexStepContext) -> None:
        """Chunk text, embed, and write to LanceDB.

        TODO: implement actual chunking + embedding.
        1. Read available text reps from OSS
        2. Split into chunks (semantic chunking with section awareness)
        3. Generate embeddings via Jina V5 / BGE
        4. Write ChunkRecords to LanceDB table
        """
        logger.info(
            f"[chunk_and_embed_text] Processing entity={ctx.entity_id} "
            f"available_reps={list(ctx.available_reps.keys())}"
        )
        # TODO: implement

    def is_built(self, ctx: IndexStepContext) -> bool:
        """Check if chunks already exist in LanceDB for this entity."""
        # TODO: query LanceDB for existing chunks
        return False

    def rebuild(self, ctx: IndexStepContext) -> None:
        """Delete old chunks and rebuild."""
        # TODO: delete from LanceDB, then execute
        self.execute(ctx)

    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_hybrid": True,
            "requires_training": False,
        }


class BuildVectorIndexStep:
    """向量索引构建 (§6.7.3): creates IVF_PQ or HNSW index on LanceDB.

    Called after chunks are written to LanceDB.
    """

    @property
    def step_id(self) -> str:
        return "build_vector_index"

    @property
    def name(self) -> str:
        return "向量索引构建"

    @property
    def index_type(self) -> str:
        return "semantic"

    @property
    def required_reps(self) -> list[str]:
        return []

    @property
    def optional_reps(self) -> list[str]:
        return []

    @property
    def supported_modalities(self) -> list[str]:
        return ["text", "image", "audio"]

    def execute(self, ctx: IndexStepContext) -> None:
        """Build vector index on LanceDB table.

        TODO: implement using lancedb table.create_index().
        v0.1: IVF_PQ for large datasets, auto-choose parameters.
        """
        logger.info(f"[build_vector_index] Processing entity={ctx.entity_id}")
        # TODO: implement
        # if ctx.lance_table:
        #     ctx.lance_table.create_index(
        #         "vector",
        #         index_type="ivf_pq",
        #         num_partitions=256,
        #         num_sub_vectors=16,
        #     )

    def is_built(self, ctx: IndexStepContext) -> bool:
        """Check if vector index already exists."""
        # TODO: check LanceDB index stats
        return False

    def rebuild(self, ctx: IndexStepContext) -> None:
        """Rebuild vector index."""
        self.execute(ctx)

    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_hybrid": True,
            "requires_training": False,
        }


class BuildFtsIndexStep:
    """全文索引构建 (§6.7.3): creates FTS index on LanceDB.

    Uses LanceDB's built-in FTS (Tantivy-based).
    """

    @property
    def step_id(self) -> str:
        return "build_fts_index"

    @property
    def name(self) -> str:
        return "全文索引构建"

    @property
    def index_type(self) -> str:
        return "lexical"

    @property
    def required_reps(self) -> list[str]:
        return []

    @property
    def optional_reps(self) -> list[str]:
        return []

    @property
    def supported_modalities(self) -> list[str]:
        return ["text"]

    def execute(self, ctx: IndexStepContext) -> None:
        """Build full-text search index.

        TODO: implement using lancedb table.create_fts_index().
        """
        logger.info(f"[build_fts_index] Processing entity={ctx.entity_id}")
        # TODO: implement
        # if ctx.lance_table:
        #     ctx.lance_table.create_fts_index("text", replace=True)

    def is_built(self, ctx: IndexStepContext) -> bool:
        """Check if FTS index already exists."""
        return False

    def rebuild(self, ctx: IndexStepContext) -> None:
        """Rebuild FTS index."""
        self.execute(ctx)

    def capabilities(self) -> dict[str, Any]:
        return {
            "supports_hybrid": True,
            "requires_training": False,
        }


# ── v0.2 Stubs ──────────────────────────────────────────


class ChunkAndEmbedImageIndexStep:
    """图片切片+嵌入 (§6.7.3): page_image → LanceDB visual chunks. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "chunk_and_embed_image"

    @property
    def name(self) -> str:
        return "图片切片+嵌入"

    @property
    def index_type(self) -> str:
        return "visual"

    @property
    def required_reps(self) -> list[str]:
        return ["page_image"]

    @property
    def optional_reps(self) -> list[str]:
        return []

    @property
    def supported_modalities(self) -> list[str]:
        return ["image"]

    def execute(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("ChunkAndEmbedImageIndexStep is v0.2")

    def is_built(self, ctx: IndexStepContext) -> bool:
        return False

    def rebuild(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("ChunkAndEmbedImageIndexStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"supports_hybrid": False, "requires_training": False}


class ChunkAndEmbedAudioIndexStep:
    """音频切片+嵌入 (§6.7.3): transcript + audio_segment → LanceDB. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "chunk_and_embed_audio"

    @property
    def name(self) -> str:
        return "音频切片+嵌入"

    @property
    def index_type(self) -> str:
        return "audio"

    @property
    def required_reps(self) -> list[str]:
        return ["transcript", "audio_segment"]

    @property
    def optional_reps(self) -> list[str]:
        return []

    @property
    def supported_modalities(self) -> list[str]:
        return ["audio"]

    def execute(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("ChunkAndEmbedAudioIndexStep is v0.2")

    def is_built(self, ctx: IndexStepContext) -> bool:
        return False

    def rebuild(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("ChunkAndEmbedAudioIndexStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"supports_hybrid": False, "requires_training": False}


class BuildGraphIndexStep:
    """图索引构建 (§6.7.3): graph_json → graph index. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "build_graph_index"

    @property
    def name(self) -> str:
        return "图索引构建"

    @property
    def index_type(self) -> str:
        return "graph"

    @property
    def required_reps(self) -> list[str]:
        return ["graph_json"]

    @property
    def optional_reps(self) -> list[str]:
        return []

    @property
    def supported_modalities(self) -> list[str]:
        return ["graph"]

    def execute(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("BuildGraphIndexStep is v0.2")

    def is_built(self, ctx: IndexStepContext) -> bool:
        return False

    def rebuild(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("BuildGraphIndexStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"supports_hybrid": False, "requires_training": False}


class ChunkAndEmbedTableIndexStep:
    """表格切片+嵌入 (§6.7.3): table_md/table_json → LanceDB. v0.2 stub."""

    @property
    def step_id(self) -> str:
        return "chunk_and_embed_table"

    @property
    def name(self) -> str:
        return "表格切片+嵌入"

    @property
    def index_type(self) -> str:
        return "table"

    @property
    def required_reps(self) -> list[str]:
        return ["table_md", "table_json"]

    @property
    def optional_reps(self) -> list[str]:
        return []

    @property
    def supported_modalities(self) -> list[str]:
        return ["table"]

    def execute(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("ChunkAndEmbedTableIndexStep is v0.2")

    def is_built(self, ctx: IndexStepContext) -> bool:
        return False

    def rebuild(self, ctx: IndexStepContext) -> None:
        raise NotImplementedError("ChunkAndEmbedTableIndexStep is v0.2")

    def capabilities(self) -> dict[str, Any]:
        return {"supports_hybrid": False, "requires_training": False}


def register_builtin_index_steps() -> None:
    """Register all built-in IndexSteps into IndexStepRegistry."""
    from vector_lake.pipeline.registry import IndexStepRegistry

    # v0.1 steps
    IndexStepRegistry.register(ChunkAndEmbedTextIndexStep())
    IndexStepRegistry.register(BuildVectorIndexStep())
    IndexStepRegistry.register(BuildFtsIndexStep())

    # v0.2 stubs
    IndexStepRegistry.register(ChunkAndEmbedImageIndexStep())
    IndexStepRegistry.register(ChunkAndEmbedAudioIndexStep())
    IndexStepRegistry.register(BuildGraphIndexStep())
    IndexStepRegistry.register(ChunkAndEmbedTableIndexStep())

    logger.info(f"Registered {len(IndexStepRegistry.all_steps())} built-in IndexSteps")
