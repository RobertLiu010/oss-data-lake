"""Pipeline orchestration: source → [step₁ → step₂ → …] → chunk → embed → index.

The pipeline is registry-driven and supports both:

- **Multi-step pipelines**: resolve a chain of RepSteps via DAG (e.g.
  docx → pdf → png → md), saving every intermediate product as a rep.
- **Legacy single-step**: use a RepTemplate directly (backward compat).

The pipeline always produces a final text representation (``canonical_md``)
that can be chunked, embedded, and indexed.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.config import Settings
from app.models.chunk import Chunk
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.event_bus import Event, EventBus, EventType
from app.services.index import IndexService
from app.services.registry import (
    DEFAULT_TARGET_FORMAT,
    IndexContext,
    RepContext,
    RepPipeline,
    SearchContext,
    StepContext,
    StepResult,
    TemplateRegistry,
)
from app.services.registry import registry as default_registry
from app.storage.protocol import StorageProtocol

logger = logging.getLogger(__name__)


class PipelineService:
    """Orchestrate the full processing pipeline for an entity.

    Multi-step flow:
        1. Resolve RepPipeline from source format → target format (default: md)
        2. Execute each RepStep in order, saving every intermediate as a rep
        3. Chunk the final text representation
        4. Embed the chunks
        5. Index the chunks via the configured IndexTemplate
    """

    def __init__(
        self,
        storage: StorageProtocol,
        chunking: ChunkingService,
        embedding: EmbeddingService,
        index: IndexService,
        settings: Settings,
        event_bus: EventBus | None = None,
        template_registry: TemplateRegistry | None = None,
    ):
        self.storage = storage
        self.chunking = chunking
        self.embedding = embedding
        self.index = index
        self.settings = settings
        self.event_bus = event_bus
        self._registry = template_registry or default_registry

    # ------------------------------------------------------------------
    # Multi-step pipeline (primary entry point)
    # ------------------------------------------------------------------

    async def process_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        filename: str,
        source_content: bytes,
        *,
        rep_template_name: str | None = None,
        index_template_name: str | None = None,
        target_format: str = DEFAULT_TARGET_FORMAT,
    ) -> list[Chunk]:
        """Process an entity through the full pipeline.

        Tries multi-step pipeline first (via RepStep DAG), falls back
        to legacy RepTemplate if no steps are registered for the format.
        """
        # Publish ENTITY_CREATED event
        if self.event_bus:
            await self.event_bus.publish(Event(
                event_type=EventType.ENTITY_CREATED,
                workspace_id=workspace_id,
                collection_id=collection_id,
                entity_id=entity_id,
            ))

        # Save source_original
        self.storage.save_file(
            workspace_id, collection_id, entity_id,
            "source_original", source_content,
        )

        # Try multi-step pipeline first
        canonical_text, pipeline_meta = await self._build_representation(
            workspace_id, collection_id, entity_id,
            filename, source_content,
            rep_template_name=rep_template_name,
            target_format=target_format,
        )

        # Chunk the final text representation
        metadata: dict[str, Any] = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
            **pipeline_meta,
        }
        chunks = await self.chunking.execute(canonical_text, metadata)
        logger.info("Pipeline: chunked into %d chunks", len(chunks))

        if not chunks:
            return chunks

        # Embed the chunks
        texts_to_embed = [c.embedding_text or c.text for c in chunks]
        try:
            vectors = await self.embedding.embed_passages(texts_to_embed)
        except Exception as exc:
            logger.warning(
                "Pipeline: embedding failed for entity %s (%s), "
                "chunks saved but not indexed",
                entity_id, exc,
            )
            if self.event_bus:
                await self.event_bus.publish(Event(
                    event_type=EventType.REP_COMPLETED,
                    workspace_id=workspace_id,
                    collection_id=collection_id,
                    entity_id=entity_id,
                    payload={"indexed": False},
                ))
            return chunks

        # Build index via IndexTemplate
        index_name = index_template_name or "vector_index"
        index_tmpl = self._registry.get_index_template(index_name)
        if index_tmpl is None:
            raise ValueError(f"IndexTemplate '{index_name}' not found")

        chunks_with_vectors: list[dict[str, Any]] = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            chunks_with_vectors.append({
                "chunk_index": idx,
                "text": chunk.text,
                "embedding": vector,
                "metadata": chunk.metadata,
            })

        try:
            idx_ctx = IndexContext(
                workspace_id=workspace_id,
                collection_id=collection_id,
                entity_id=entity_id,
                chunks=chunks_with_vectors,
                index_service=self.index,
                settings=self.settings,
            )
            await index_tmpl.build(idx_ctx)
            logger.info("Pipeline: indexed %d chunks for entity %s", len(chunks), entity_id)
            if self.event_bus:
                await self.event_bus.publish(Event(
                    event_type=EventType.INDEX_COMPLETED,
                    workspace_id=workspace_id,
                    collection_id=collection_id,
                    entity_id=entity_id,
                    payload={"chunk_count": len(chunks)},
                ))
        except Exception as exc:
            logger.warning(
                "Pipeline: index build failed for entity %s (%s), "
                "chunks saved but not searchable",
                entity_id, exc,
            )
            if self.event_bus:
                await self.event_bus.publish(Event(
                    event_type=EventType.REP_COMPLETED,
                    workspace_id=workspace_id,
                    collection_id=collection_id,
                    entity_id=entity_id,
                    payload={"indexed": False},
                ))

        return chunks

    # ------------------------------------------------------------------
    # Representation building — multi-step or legacy
    # ------------------------------------------------------------------

    async def _build_representation(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        filename: str,
        source_content: bytes,
        *,
        rep_template_name: str | None = None,
        target_format: str = DEFAULT_TARGET_FORMAT,
    ) -> tuple[str, dict[str, Any]]:
        """Build the canonical text representation.

        Returns (canonical_text, metadata_dict).

        Tries multi-step pipeline first, falls back to legacy RepTemplate.
        """
        # Try multi-step pipeline via DAG resolution
        pipeline = None
        if rep_template_name is None:
            try:
                pipeline = self._registry.resolve_pipeline_for_file(
                    filename, target_format,
                )
            except ValueError:
                pipeline = None

        if pipeline is not None:
            return await self._execute_step_pipeline(
                workspace_id, collection_id, entity_id,
                source_content, pipeline,
            )

        # Fall back to legacy RepTemplate
        if rep_template_name:
            rep_tmpl = self._registry.get_rep_template(rep_template_name)
            if rep_tmpl is None:
                raise ValueError(f"RepTemplate '{rep_template_name}' not found")
        else:
            rep_tmpl = self._registry.find_rep_template_for_file(filename)
            if rep_tmpl is None:
                raise ValueError(
                    f"No RepTemplate or RepStep pipeline registered for "
                    f"file '{filename}'"
                )

        rep_ctx = RepContext(
            workspace_id=workspace_id,
            collection_id=collection_id,
            entity_id=entity_id,
            filename=filename,
            source_content=source_content,
            storage=self.storage,
            settings=self.settings,
        )
        rep_result = await rep_tmpl.build(rep_ctx)

        # Save the primary representation
        self.storage.save_file(
            workspace_id, collection_id, entity_id,
            rep_result.rep_type, rep_result.content,
        )

        # Save any extra representations
        for extra_rep_type, extra_content in rep_result.extra_reps.items():
            self.storage.save_file(
                workspace_id, collection_id, entity_id,
                extra_rep_type, extra_content,
            )

        canonical_text = rep_result.content.decode("utf-8", errors="replace")
        return canonical_text, rep_result.metadata

    async def _execute_step_pipeline(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        source_content: bytes,
        pipeline: RepPipeline,
    ) -> tuple[str, dict[str, Any]]:
        """Execute a resolved RepPipeline step by step.

        Each step's output is saved as a rep file:
        - Step 0 output → ``rep_{output_format}`` (e.g. rep_pdf, rep_png)
        - Final step output → ``canonical_md`` (the chunkable text)

        If a step declares ``index_mode``, its output is also indexed
        independently (chunked + embedded + indexed) right after the step
        executes.  This allows intermediate products like PDF text to be
        searchable even before the full pipeline completes.

        Returns (canonical_text, metadata_dict).
        """
        current_content = source_content
        current_format = pipeline.source_format
        all_metadata: dict[str, Any] = {
            "pipeline": pipeline.describe(),
            "pipeline_steps": pipeline.step_names,
            "intermediate_reps": [],
        }

        logger.info(
            "Pipeline: executing %d-step pipeline for entity %s: %s",
            len(pipeline.steps), entity_id, pipeline.describe(),
        )

        # Identity pipeline (source_format == target_format, no steps)
        if not pipeline.steps:
            canonical_text = current_content.decode("utf-8", errors="replace")
            # Save as canonical_md
            self.storage.save_file(
                workspace_id, collection_id, entity_id,
                "canonical_md", current_content,
            )
            all_metadata["transform"] = "passthru"
            return canonical_text, all_metadata

        for i, step in enumerate(pipeline.steps):
            is_last = i == len(pipeline.steps) - 1
            step_ctx = StepContext(
                workspace_id=workspace_id,
                collection_id=collection_id,
                entity_id=entity_id,
                input_content=current_content,
                input_format=current_format,
                step_index=i,
                storage=self.storage,
                settings=self.settings,
            )

            step_result = await step.transform(step_ctx)

            # Determine rep name
            if is_last:
                # Final step → canonical_md (chunkable text)
                rep_name = "canonical_md"
            else:
                # Intermediate step → rep_{format}
                rep_name = f"rep_{step_result.output_format}"

            # Save the intermediate/final product
            self.storage.save_file(
                workspace_id, collection_id, entity_id,
                rep_name, step_result.content,
            )

            # Per-step indexing: if the step declares index_mode,
            # index its output independently.
            index_mode = getattr(step, "index_mode", None)
            step_indexed = False
            if index_mode and not is_last:
                step_indexed = await self._index_step_output(
                    workspace_id, collection_id, entity_id,
                    step_result, rep_name, index_mode,
                )

            all_metadata["intermediate_reps"].append({
                "step": step.name,
                "step_index": i,
                "input_format": current_format,
                "output_format": step_result.output_format,
                "rep_name": rep_name,
                "size_bytes": len(step_result.content),
                "index_mode": index_mode,
                "indexed": step_indexed,
            })
            all_metadata.update(step_result.metadata)

            logger.info(
                "Pipeline: step %d/%d (%s) %s → %s, saved as %s (%d bytes)%s",
                i + 1, len(pipeline.steps), step.name,
                current_format, step_result.output_format,
                rep_name, len(step_result.content),
                f", indexed={step_indexed}" if index_mode else "",
            )

            current_content = step_result.content
            current_format = step_result.output_format

        # Final content should be text (md format)
        canonical_text = current_content.decode("utf-8", errors="replace")
        all_metadata["content_hash"] = hashlib.sha256(current_content).hexdigest()[:16]
        all_metadata["modality"] = "text"

        return canonical_text, all_metadata

    async def _index_step_output(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        step_result: StepResult,
        rep_name: str,
        index_mode: str,
    ) -> bool:
        """Index a step's output independently.

        Returns True if indexing succeeded, False otherwise.
        """
        # Get the text to index
        text = step_result.indexable_text
        if text is None:
            # Try to decode content as text
            try:
                text = step_result.content.decode("utf-8", errors="replace")
            except Exception:
                logger.warning(
                    "Step output %s has no indexable_text and content is not text",
                    rep_name,
                )
                return False

        if not text.strip():
            return False

        # Chunk the text
        metadata: dict[str, Any] = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
            "rep_name": rep_name,
            "source_step": step_result.metadata.get("step", ""),
            **step_result.metadata,
        }
        chunks = await self.chunking.execute(text, metadata)
        if not chunks:
            return False

        if index_mode == "lexical":
            # FTS-only indexing — no embeddings needed
            try:
                chunks_for_index = [
                    {
                        "chunk_index": idx,
                        "text": c.text,
                        "embedding": [],
                        "metadata": c.metadata,
                    }
                    for idx, c in enumerate(chunks)
                ]
                await self.index.upsert_chunks(
                    workspace_id, collection_id, entity_id,
                    chunks_for_index,
                )
                logger.info(
                    "Per-step index: %d chunks indexed (lexical) for rep %s",
                    len(chunks), rep_name,
                )
                return True
            except Exception as exc:
                logger.warning(
                    "Per-step lexical index failed for rep %s: %s",
                    rep_name, exc,
                )
                return False

        # index_mode == "text" (default) — embed + vector index
        texts_to_embed = [c.embedding_text or c.text for c in chunks]
        try:
            vectors = await self.embedding.embed_passages(texts_to_embed)
        except Exception as exc:
            logger.warning(
                "Per-step embedding failed for rep %s: %s", rep_name, exc,
            )
            return False

        chunks_with_vectors: list[dict[str, Any]] = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            chunks_with_vectors.append({
                "chunk_index": idx,
                "text": chunk.text,
                "embedding": vector,
                "metadata": chunk.metadata,
            })

        try:
            await self.index.upsert_chunks(
                workspace_id, collection_id, entity_id,
                chunks_with_vectors,
            )
            logger.info(
                "Per-step index: %d chunks indexed (vector) for rep %s",
                len(chunks), rep_name,
            )
            return True
        except Exception as exc:
            logger.warning(
                "Per-step vector index failed for rep %s: %s", rep_name, exc,
            )
            return False

    # ------------------------------------------------------------------
    # Legacy convenience method (backward compat)
    # ------------------------------------------------------------------

    async def process_md_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        md_content: str,
    ) -> list[Chunk]:
        """Full pipeline: MD → canonical_md → chunk → embed → index.

        Convenience wrapper around process_entity() for the common MD case.
        """
        return await self.process_entity(
            workspace_id=workspace_id,
            collection_id=collection_id,
            entity_id=entity_id,
            filename="source.md",
            source_content=md_content.encode("utf-8"),
        )

    # ------------------------------------------------------------------
    # Search via IndexTemplate
    # ------------------------------------------------------------------

    async def search_with_template(
        self,
        workspace_id: str,
        collection_id: str,
        query: str,
        query_vector: list[float] | None = None,
        *,
        index_template_name: str = "vector_index",
        top_k: int = 5,
        **params: Any,
    ) -> list[Chunk]:
        """Search using a named IndexTemplate."""
        index_tmpl = self._registry.get_index_template(index_template_name)
        if index_tmpl is None:
            raise ValueError(f"IndexTemplate '{index_template_name}' not found")

        search_ctx = SearchContext(
            workspace_id=workspace_id,
            collection_id=collection_id,
            query=query,
            query_vector=query_vector,
            top_k=top_k,
            index_service=self.index,
            settings=self.settings,
            params=params,
        )
        return await index_tmpl.search(search_ctx)
