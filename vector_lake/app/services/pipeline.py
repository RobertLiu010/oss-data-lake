"""Pipeline orchestration: source → [step₁ → step₂ → …] → chunk → embed → index.

Per PRD §2.6 the pipeline is split into two independent sub-pipelines:

- **RepPipelineService** — content transformation (source → reps).
  Resolves a RepPipeline via the registry, executes each RepStep, saves
  intermediates with lineage paths, and publishes ``REP_COMPLETED``.
  Does NOT access EmbeddingService or IndexService.

- **IndexPipelineService** — index construction (reps → chunks → index).
  Chunks text, embeds chunks, indexes via IndexTemplate, and publishes
  ``INDEX_COMPLETED``.  Also provides ``index_rep()`` for indexing
  intermediate rep products independently.

- **PipelineService** — thin orchestrator that calls RepPipeline then
  IndexPipeline.  Maintains backward-compatible ``process_entity()``
  and ``process_md_entity()`` signatures.
"""

from __future__ import annotations

import asyncio
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
from app.services.sync_queue import SyncQueue, SyncTask
from app.storage.protocol import StorageProtocol

logger = logging.getLogger(__name__)


# ======================================================================
# RepPipelineService — content transformation only
# ======================================================================


class RepPipelineService:
    """Handle content transformation: source → reps.

    Executes the RepPipeline (multi-step or legacy RepTemplate), saves
    every intermediate product as a rep file, and publishes
    ``REP_COMPLETED`` when all reps are ready.

    Does NOT access EmbeddingService or IndexService — indexing is
    IndexPipelineService's job.
    """

    def __init__(
        self,
        storage: StorageProtocol,
        settings: Settings,
        event_bus: EventBus | None = None,
        template_registry: TemplateRegistry | None = None,
    ):
        self.storage = storage
        self.settings = settings
        self.event_bus = event_bus
        self._registry = template_registry or default_registry

    async def run_rep_pipeline(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        filename: str,
        source_content: bytes,
        *,
        rep_template_name: str | None = None,
        target_format: str = DEFAULT_TARGET_FORMAT,
    ) -> dict[str, Any]:
        """Run the representation pipeline.

        Returns a dict with:
        - ``canonical_text``: the final text representation
        - ``metadata``: pipeline metadata including intermediate rep info
        - ``rep_files``: list of dicts describing each rep file, with keys
          ``rep_name``, ``output_format``, ``index_mode``, ``indexable_text``,
          ``step_index``, ``step_name``
        """
        # Save source_original
        self.storage.save_file(
            workspace_id, collection_id, entity_id,
            "source_original", source_content,
        )

        # Build representation (multi-step or legacy)
        canonical_text, pipeline_meta = await self._build_representation(
            workspace_id, collection_id, entity_id,
            filename, source_content,
            rep_template_name=rep_template_name,
            target_format=target_format,
        )

        # Build rep_files list from intermediate_reps metadata
        rep_files: list[dict[str, Any]] = []
        for rep_info in pipeline_meta.get("intermediate_reps", []):
            rep_files.append({
                "rep_name": rep_info["rep_name"],
                "output_format": rep_info.get("output_format", ""),
                "index_mode": rep_info.get("index_mode"),
                "indexable_text": rep_info.get("indexable_text"),
                "step_index": rep_info.get("step_index", 0),
                "step_name": rep_info.get("step", ""),
            })

        return {
            "canonical_text": canonical_text,
            "metadata": pipeline_meta,
            "rep_files": rep_files,
        }

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

        # Set Rep Tags for primary rep
        primary_hash = hashlib.sha256(rep_result.content).hexdigest()[:16]
        source_hash = hashlib.sha256(source_content).hexdigest()[:16]
        self.storage.set_rep_tags(
            workspace_id, collection_id, entity_id, rep_result.rep_type,
            {
                "rep_type": rep_result.rep_type,
                "transform": rep_tmpl.name if hasattr(rep_tmpl, "name") else "legacy",
                "pipeline_id": "",
                "pipeline_version": "1",
                "input_content_hash": source_hash,
                "content_hash": primary_hash,
                "status": "active",
                "modality": "text",
                "model_version": "",
            },
        )

        # Save any extra representations
        for extra_rep_type, extra_content in rep_result.extra_reps.items():
            self.storage.save_file(
                workspace_id, collection_id, entity_id,
                extra_rep_type, extra_content,
            )
            # Set Rep Tags for extra rep
            extra_hash = hashlib.sha256(extra_content).hexdigest()[:16]
            self.storage.set_rep_tags(
                workspace_id, collection_id, entity_id, extra_rep_type,
                {
                    "rep_type": extra_rep_type,
                    "transform": rep_tmpl.name if hasattr(rep_tmpl, "name") else "legacy",
                    "pipeline_id": "",
                    "pipeline_version": "1",
                    "input_content_hash": source_hash,
                    "content_hash": extra_hash,
                    "status": "active",
                    "modality": "text",
                    "model_version": "",
                },
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

        Per-step indexing is NOT performed here — that is IndexPipeline's
        job.  However, the metadata records each step's ``index_mode`` and
        ``indexable_text`` so the orchestrator can delegate indexing to
        IndexPipelineService.

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
            "RepPipeline: executing %d-step pipeline for entity %s: %s",
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
            # Set Rep Tags for passthru
            content_hash = hashlib.sha256(current_content).hexdigest()[:16]
            self.storage.set_rep_tags(
                workspace_id, collection_id, entity_id, "canonical_md",
                {
                    "rep_type": "canonical_md",
                    "transform": "passthru",
                    "pipeline_id": "",
                    "pipeline_version": "1",
                    "input_content_hash": content_hash,
                    "content_hash": content_hash,
                    "status": "active",
                    "modality": "text",
                    "model_version": "",
                },
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

            # Set Rep Tags with all 9 fields
            rep_content_hash = hashlib.sha256(step_result.content).hexdigest()[:16]
            input_hash = hashlib.sha256(current_content).hexdigest()[:16] if current_content != source_content else ""
            # For the first step, input is source_original
            if i == 0:
                input_hash = hashlib.sha256(source_content).hexdigest()[:16]

            # Determine modality from output format
            modality = "text"
            if step_result.output_format in ("png", "jpg", "jpeg", "tiff", "bmp", "gif", "webp", "svg", "heic", "avif"):
                modality = "image"
            elif step_result.output_format in ("wav", "mp3", "flac", "ogg", "m4a", "opus"):
                modality = "audio"
            elif step_result.output_format in ("mp4", "avi", "mov", "mkv", "webm", "flv", "wmv"):
                modality = "video"
            elif step_result.output_format in ("csv", "tsv", "xlsx", "xls", "parquet"):
                modality = "table"

            self.storage.set_rep_tags(
                workspace_id, collection_id, entity_id, rep_name,
                {
                    "rep_type": rep_name,
                    "transform": step.name,
                    "pipeline_id": pipeline.describe(),
                    "pipeline_version": "1",
                    "input_content_hash": input_hash,
                    "content_hash": rep_content_hash,
                    "status": "active",
                    "modality": modality,
                    "model_version": "",
                },
            )

            # Determine indexable text for this step (for metadata only;
            # actual indexing is done by IndexPipelineService)
            index_mode = getattr(step, "index_mode", None)
            indexable_text: str | None = None
            if index_mode and not is_last:
                indexable_text = step_result.indexable_text
                if indexable_text is None:
                    try:
                        indexable_text = step_result.content.decode(
                            "utf-8", errors="replace",
                        )
                    except Exception:
                        indexable_text = None

            all_metadata["intermediate_reps"].append({
                "step": step.name,
                "step_index": i,
                "input_format": current_format,
                "output_format": step_result.output_format,
                "rep_name": rep_name,
                "size_bytes": len(step_result.content),
                "index_mode": index_mode,
                "indexable_text": indexable_text,
            })
            all_metadata.update(step_result.metadata)

            logger.info(
                "RepPipeline: step %d/%d (%s) %s → %s, saved as %s (%d bytes)",
                i + 1, len(pipeline.steps), step.name,
                current_format, step_result.output_format,
                rep_name, len(step_result.content),
            )

            current_content = step_result.content
            current_format = step_result.output_format

        # Final content should be text (md format)
        canonical_text = current_content.decode("utf-8", errors="replace")
        all_metadata["content_hash"] = hashlib.sha256(current_content).hexdigest()[:16]
        all_metadata["modality"] = "text"

        return canonical_text, all_metadata


# ======================================================================
# IndexPipelineService — index construction only
# ======================================================================


class IndexPipelineService:
    """Handle index construction: reps → chunks → index.

    Chunks text, embeds chunks, indexes via IndexTemplate, and publishes
    ``INDEX_COMPLETED``.  Also provides ``index_rep()`` for indexing
    intermediate rep products independently.

    Needs ChunkingService, EmbeddingService, IndexService.
    Does NOT access StorageProtocol.
    """

    def __init__(
        self,
        chunking: ChunkingService,
        embedding: EmbeddingService,
        index: IndexService,
        settings: Settings,
        event_bus: EventBus | None = None,
        template_registry: TemplateRegistry | None = None,
        sync_queue: SyncQueue | None = None,
    ):
        self.chunking = chunking
        self.embedding = embedding
        self.index = index
        self.settings = settings
        self.event_bus = event_bus
        self._registry = template_registry or default_registry
        self.sync_queue = sync_queue

    async def run_index_pipeline(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        canonical_text: str,
        metadata: dict[str, Any],
        *,
        index_template_name: str | None = None,
    ) -> list[Chunk]:
        """Run the index pipeline: chunk → embed → index.

        Returns the list of Chunk objects produced.
        """
        # Chunk the final text representation
        chunk_metadata: dict[str, Any] = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
            **metadata,
        }
        chunks = await self.chunking.execute(canonical_text, chunk_metadata)
        logger.info("IndexPipeline: chunked into %d chunks", len(chunks))

        if not chunks:
            return chunks

        # Embed the chunks
        texts_to_embed = [c.embedding_text or c.text for c in chunks]
        try:
            vectors = await self.embedding.embed_passages(texts_to_embed)
        except Exception as exc:
            logger.warning(
                "IndexPipeline: embedding failed for entity %s (%s), "
                "chunks saved but not indexed",
                entity_id, exc,
            )
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
                "embedding_text": chunk.embedding_text or chunk.text,
                "embedding": vector,
                "metadata": chunk.metadata,
                "rep_name": "canonical_md",
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
            logger.info(
                "IndexPipeline: indexed %d chunks for entity %s",
                len(chunks), entity_id,
            )
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
                "IndexPipeline: index build failed for entity %s (%s), "
                "chunks saved but not searchable",
                entity_id, exc,
            )

        return chunks

    async def index_rep(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_name: str,
        text: str,
        index_mode: str,
    ) -> bool:
        """Index a single rep independently (for intermediate products).

        Returns True if indexing succeeded, False otherwise.
        """
        if not text.strip():
            return False

        # Chunk the text
        metadata: dict[str, Any] = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
            "rep_name": rep_name,
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
                        "embedding_text": c.embedding_text or c.text,
                        "embedding": [],
                        "metadata": c.metadata,
                        "rep_name": rep_name,
                    }
                    for idx, c in enumerate(chunks)
                ]
                await self.index.upsert_chunks(
                    workspace_id, collection_id, entity_id,
                    chunks_for_index,
                    rep_name=rep_name,
                )
                # Enqueue sync task (parquet → LanceDB)
                self._enqueue_sync(workspace_id, collection_id, entity_id, rep_name)
                logger.info(
                    "IndexPipeline: %d chunks indexed (lexical) for rep %s",
                    len(chunks), rep_name,
                )
                return True
            except Exception as exc:
                logger.warning(
                    "IndexPipeline: lexical index failed for rep %s: %s",
                    rep_name, exc,
                )
                return False

        # index_mode == "text" (default) — embed + vector index
        texts_to_embed = [c.embedding_text or c.text for c in chunks]
        try:
            vectors = await self.embedding.embed_passages(texts_to_embed)
        except Exception as exc:
            logger.warning(
                "IndexPipeline: embedding failed for rep %s: %s",
                rep_name, exc,
            )
            return False

        chunks_with_vectors: list[dict[str, Any]] = []
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            chunks_with_vectors.append({
                "chunk_index": idx,
                "text": chunk.text,
                "embedding_text": chunk.embedding_text or chunk.text,
                "embedding": vector,
                "metadata": chunk.metadata,
                "rep_name": rep_name,
            })

        try:
            await self.index.upsert_chunks(
                workspace_id, collection_id, entity_id,
                chunks_with_vectors,
                rep_name=rep_name,
            )
            # Enqueue sync task (parquet → LanceDB)
            self._enqueue_sync(workspace_id, collection_id, entity_id, rep_name)
            logger.info(
                "IndexPipeline: %d chunks indexed (vector) for rep %s",
                len(chunks), rep_name,
            )
            return True
        except Exception as exc:
            logger.warning(
                "IndexPipeline: vector index failed for rep %s: %s",
                rep_name, exc,
            )
            return False

    def _enqueue_sync(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_name: str,
    ) -> None:
        """Enqueue a parquet → LanceDB sync task.

        If sync_queue is available, enqueues for async processing.
        Otherwise, falls back to direct sync (backward compat for tests).
        """
        if self.sync_queue is not None:
            task = SyncTask(
                workspace_id=workspace_id,
                collection_id=collection_id,
                entity_id=entity_id,
                rep_name=rep_name,
            )
            asyncio.ensure_future(self.sync_queue.enqueue(task))
        else:
            # Fallback: direct sync (for tests without sync_queue)
            asyncio.ensure_future(
                self.index.sync_to_lance(workspace_id, collection_id, entity_id, rep_name)
            )


# ======================================================================
# PipelineService — thin orchestrator
# ======================================================================


class PipelineService:
    """Orchestrate the full processing pipeline for an entity.

    Delegates to RepPipelineService for content transformation and
    IndexPipelineService for index construction, maintaining backward-
    compatible ``process_entity()`` and ``process_md_entity()`` signatures.
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
        sync_queue: SyncQueue | None = None,
    ):
        self._storage = storage
        self._chunking = chunking
        self._embedding = embedding
        self._index = index
        self._settings = settings
        self._event_bus = event_bus
        self._registry = template_registry or default_registry
        self._sync_queue = sync_queue

        # Create sub-services sharing the same registry
        self.rep_pipeline = RepPipelineService(
            storage, settings, event_bus, self._registry,
        )
        self.index_pipeline = IndexPipelineService(
            chunking, embedding, index, settings, event_bus, self._registry,
            sync_queue=sync_queue,
        )

    # -- Properties that sync to sub-services for backward compat --------
    # Tests sometimes mock pipeline_service.embedding / .index directly;
    # these setters propagate the change to the sub-services.

    @property
    def storage(self) -> StorageProtocol:
        return self._storage

    @storage.setter
    def storage(self, value: StorageProtocol) -> None:
        self._storage = value
        if hasattr(self, "rep_pipeline"):
            self.rep_pipeline.storage = value

    @property
    def chunking(self) -> ChunkingService:
        return self._chunking

    @chunking.setter
    def chunking(self, value: ChunkingService) -> None:
        self._chunking = value
        if hasattr(self, "index_pipeline"):
            self.index_pipeline.chunking = value

    @property
    def embedding(self) -> EmbeddingService:
        return self._embedding

    @embedding.setter
    def embedding(self, value: EmbeddingService) -> None:
        self._embedding = value
        if hasattr(self, "index_pipeline"):
            self.index_pipeline.embedding = value

    @property
    def index(self) -> IndexService:
        return self._index

    @index.setter
    def index(self, value: IndexService) -> None:
        self._index = value
        if hasattr(self, "index_pipeline"):
            self.index_pipeline.index = value

    @property
    def settings(self) -> Settings:
        return self._settings

    @settings.setter
    def settings(self, value: Settings) -> None:
        self._settings = value
        if hasattr(self, "rep_pipeline"):
            self.rep_pipeline.settings = value
        if hasattr(self, "index_pipeline"):
            self.index_pipeline.settings = value

    @property
    def event_bus(self) -> EventBus | None:
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value: EventBus | None) -> None:
        self._event_bus = value
        if hasattr(self, "rep_pipeline"):
            self.rep_pipeline.event_bus = value
        if hasattr(self, "index_pipeline"):
            self.index_pipeline.event_bus = value

    # ------------------------------------------------------------------
    # Primary entry point (backward compatible)
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

        1. Publish ENTITY_CREATED event
        2. Run RepPipeline (source → reps)
        3. Index intermediate reps that declare index_mode
        4. Run IndexPipeline (canonical text → chunks → index)
        """
        # Publish ENTITY_CREATED event
        if self.event_bus:
            await self.event_bus.publish(Event(
                event_type=EventType.ENTITY_CREATED,
                workspace_id=workspace_id,
                collection_id=collection_id,
                entity_id=entity_id,
            ))

        # Step 1: Run RepPipeline
        rep_result = await self.rep_pipeline.run_rep_pipeline(
            workspace_id, collection_id, entity_id,
            filename, source_content,
            rep_template_name=rep_template_name,
            target_format=target_format,
        )

        # Step 2: Index intermediate reps that declare index_mode.
        # Skip the final step (canonical_md) — it is indexed by the
        # main IndexPipeline below, not per-step.
        for rep_file in rep_result.get("rep_files", []):
            index_mode = rep_file.get("index_mode")
            is_final = rep_file.get("rep_name") == "canonical_md"
            if index_mode and not is_final:
                indexable_text = rep_file.get("indexable_text")
                if indexable_text is None:
                    # Fallback: read rep content from storage and decode
                    rep_content = self.storage.read_file(
                        workspace_id, collection_id, entity_id,
                        rep_file["rep_name"],
                    )
                    if rep_content is not None:
                        try:
                            indexable_text = rep_content.decode(
                                "utf-8", errors="replace",
                            )
                        except Exception:
                            logger.warning(
                                "Could not decode rep %s for indexing",
                                rep_file["rep_name"],
                            )

                if indexable_text:
                    step_result = StepResult(
                        content=indexable_text.encode("utf-8"),
                        output_format=rep_file.get("output_format", ""),
                        indexable_text=indexable_text,
                    )
                    await self._index_step_output(
                        workspace_id, collection_id, entity_id,
                        step_result, rep_file["rep_name"], index_mode,
                    )

        # Step 3: Run IndexPipeline on canonical text.
        # We intercept embedding/index failures to publish the
        # backward-compat REP_COMPLETED event with indexed=False.
        chunk_metadata: dict[str, Any] = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
            **rep_result["metadata"],
        }
        chunks = await self.chunking.execute(
            rep_result["canonical_text"], chunk_metadata,
        )
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
                "embedding_text": chunk.embedding_text or chunk.text,
                "embedding": vector,
                "metadata": chunk.metadata,
                "rep_name": "canonical_md",
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
            logger.info(
                "Pipeline: indexed %d chunks for entity %s",
                len(chunks), entity_id,
            )
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

    # ------------------------------------------------------------------
    # Backward-compat shims — delegate to sub-services
    # ------------------------------------------------------------------

    async def _execute_step_pipeline(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        source_content: bytes,
        pipeline: RepPipeline,
    ) -> tuple[str, dict[str, Any]]:
        """Backward-compat shim: runs RepPipeline then indexes intermediate reps.

        Replicates the old monolithic behavior where per-step indexing was
        done inside the step pipeline execution, so that existing tests that
        patch ``_index_step_output`` continue to work.
        """
        canonical_text, metadata = await self.rep_pipeline._execute_step_pipeline(
            workspace_id, collection_id, entity_id,
            source_content, pipeline,
        )

        # Per-step indexing: for each intermediate rep with index_mode,
        # call _index_step_output and record the result in metadata.
        for rep_info in metadata.get("intermediate_reps", []):
            index_mode = rep_info.get("index_mode")
            is_last = rep_info.get("rep_name") == "canonical_md"
            if index_mode and not is_last:
                indexable_text = rep_info.get("indexable_text")
                if indexable_text is None:
                    # Read from storage and decode
                    rep_content = self.storage.read_file(
                        workspace_id, collection_id, entity_id,
                        rep_info["rep_name"],
                    )
                    if rep_content is not None:
                        try:
                            indexable_text = rep_content.decode(
                                "utf-8", errors="replace",
                            )
                        except Exception:
                            indexable_text = None

                step_indexed = False
                if indexable_text and indexable_text.strip():
                    step_result = StepResult(
                        content=indexable_text.encode("utf-8"),
                        output_format=rep_info.get("output_format", ""),
                        indexable_text=indexable_text,
                    )
                    step_indexed = await self._index_step_output(
                        workspace_id, collection_id, entity_id,
                        step_result, rep_info["rep_name"], index_mode,
                    )
                rep_info["indexed"] = step_indexed
            else:
                rep_info["indexed"] = False

        return canonical_text, metadata

    async def _index_step_output(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        step_result: StepResult,
        rep_name: str,
        index_mode: str,
    ) -> bool:
        """Backward-compat shim: indexes a step's output independently.

        Uses ``self.embedding`` and ``self.index`` directly (not the
        sub-service) so that test mocks on PipelineService attributes
        continue to work.  The clean API is
        ``IndexPipelineService.index_rep()``.
        """
        # Get the text to index
        text = step_result.indexable_text
        if text is None:
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
                        "embedding_text": c.embedding_text or c.text,
                        "embedding": [],
                        "metadata": c.metadata,
                        "rep_name": rep_name,
                    }
                    for idx, c in enumerate(chunks)
                ]
                await self.index.upsert_chunks(
                    workspace_id, collection_id, entity_id,
                    chunks_for_index,
                    rep_name=rep_name,
                )
                # Enqueue sync task (parquet → LanceDB)
                self.index_pipeline._enqueue_sync(workspace_id, collection_id, entity_id, rep_name)
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
                "embedding_text": chunk.embedding_text or chunk.text,
                "embedding": vector,
                "metadata": chunk.metadata,
                "rep_name": rep_name,
            })

        try:
            await self.index.upsert_chunks(
                workspace_id, collection_id, entity_id,
                chunks_with_vectors,
                rep_name=rep_name,
            )
            # Enqueue sync task (parquet → LanceDB)
            self.index_pipeline._enqueue_sync(workspace_id, collection_id, entity_id, rep_name)
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
