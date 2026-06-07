"""Pipeline orchestration: source → rep → chunk → embed → index.

The pipeline is now registry-driven: it looks up the appropriate
RepTemplate by file extension and the IndexTemplate by name, so new
file types and index strategies can be added without modifying this file.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.models.chunk import Chunk
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.event_bus import Event, EventBus, EventType
from app.services.index import IndexService
from app.services.registry import (
    IndexContext,
    RepContext,
    SearchContext,
    TemplateRegistry,
)
from app.services.registry import (
    registry as default_registry,
)
from app.storage.protocol import StorageProtocol

logger = logging.getLogger(__name__)


class PipelineService:
    """Orchestrate the full processing pipeline for an entity.

    The pipeline is driven by the TemplateRegistry:
    1. Find the RepTemplate for the file extension
    2. Build the representation (source → rep)
    3. Chunk the representation text
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
    # Generic pipeline (registry-driven)
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
    ) -> list[Chunk]:
        """Generic pipeline: source → rep → chunk → embed → index.

        Resolves the RepTemplate by filename extension (or by explicit
        *rep_template_name*) and the IndexTemplate by name (or defaults
        to the first registered vector index template).
        """
        # 1. Resolve RepTemplate
        if rep_template_name:
            rep_tmpl = self._registry.get_rep_template(rep_template_name)
            if rep_tmpl is None:
                raise ValueError(f"RepTemplate '{rep_template_name}' not found")
        else:
            rep_tmpl = self._registry.find_rep_template_for_file(filename)
            if rep_tmpl is None:
                raise ValueError(
                    f"No RepTemplate registered for file extension "
                    f"'{filename.rsplit('.', 1)[-1] if '.' in filename else filename}'"
                )

        # 2. Resolve IndexTemplate
        index_name = index_template_name or "vector_index"
        index_tmpl = self._registry.get_index_template(index_name)
        if index_tmpl is None:
            raise ValueError(f"IndexTemplate '{index_name}' not found")

        logger.info(
            "Pipeline: processing entity %s (%d bytes, rep=%s, index=%s)",
            entity_id, len(source_content), rep_tmpl.name, index_tmpl.name,
        )

        # Publish ENTITY_CREATED event
        if self.event_bus:
            await self.event_bus.publish(Event(
                event_type=EventType.ENTITY_CREATED,
                workspace_id=workspace_id,
                collection_id=collection_id,
                entity_id=entity_id,
            ))

        # 3. Build representation
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

        # 4. Chunk the representation text
        canonical_text = rep_result.content.decode("utf-8", errors="replace")
        metadata: dict[str, Any] = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
            **rep_result.metadata,
        }
        chunks = await self.chunking.execute(canonical_text, metadata)
        logger.info("Pipeline: chunked into %d chunks", len(chunks))

        if not chunks:
            return chunks

        # 5. Embed the chunks (batch)
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

        # 6. Build index via IndexTemplate
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
