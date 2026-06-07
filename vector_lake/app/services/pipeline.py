"""Pipeline orchestration: MD → canonical_md → chunk → embed → index."""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.models.chunk import Chunk
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.event_bus import Event, EventBus, EventType
from app.services.index import IndexService
from app.storage.protocol import StorageProtocol

logger = logging.getLogger(__name__)


class PipelineService:
    """Orchestrate the full processing pipeline for an entity."""

    def __init__(
        self,
        storage: StorageProtocol,
        chunking: ChunkingService,
        embedding: EmbeddingService,
        index: IndexService,
        settings: Settings,
        event_bus: EventBus | None = None,
    ):
        self.storage = storage
        self.chunking = chunking
        self.embedding = embedding
        self.index = index
        self.settings = settings
        self.event_bus = event_bus

    async def process_md_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        md_content: str,
    ) -> list[Chunk]:
        """Full pipeline: MD → canonical_md → chunk → embed → index.

        Returns the list of chunks (with embeddings applied).
        """
        logger.info(
            "Pipeline: processing entity %s (%d chars)",
            entity_id, len(md_content),
        )

        # Publish ENTITY_CREATED event
        if self.event_bus:
            await self.event_bus.publish(Event(
                event_type=EventType.ENTITY_CREATED,
                workspace_id=workspace_id,
                collection_id=collection_id,
                entity_id=entity_id,
            ))

        # 1. Save raw MD as source/original
        self.storage.save_file(
            workspace_id, collection_id, entity_id,
            "source_original", md_content.encode("utf-8"),
        )

        # 2. For .md files, canonical_md = md_content (no transformation)
        canonical_md = md_content
        self.storage.save_file(
            workspace_id, collection_id, entity_id,
            "canonical_md", canonical_md.encode("utf-8"),
        )

        # 3. Chunk the canonical_md
        metadata: dict[str, Any] = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
        }
        chunks = await self.chunking.execute(canonical_md, metadata)
        logger.info("Pipeline: chunked into %d chunks", len(chunks))

        if not chunks:
            return chunks

        # 4. Embed the chunks (batch)
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

        # 5. Upsert to LanceDB
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
                "Pipeline: index upsert failed for entity %s (%s), "
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
