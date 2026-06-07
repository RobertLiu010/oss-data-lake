"""Entity business logic.

Entity attributes assembled from manifest (source of truth) or xattr (fallback):
- .entity_manifest.json is the single source of truth for ALL entity fields
- Entity Tag (7 keys) on source_original: rag_status, entity_type, name, content_hash, version, labels, model_version
- xattr tags serve as optional cache, synced from manifest after every write
- Write order: manifest first (fsync), then tags (best-effort cache)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from app.config import Settings
from app.models.entity import Entity, EntityStatus, PipelineStatus, RepInfo, SourceType
from app.services.pipeline import PipelineService
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

# Known rep_types for v0.1 MD entities
KNOWN_REP_TYPES = ["source_original", "canonical_md"]


class EntityService:
    """CRUD + pipeline trigger for entities."""

    def __init__(
        self,
        storage: LocalStorage,
        pipeline: PipelineService,
        settings: Settings,
    ):
        self.storage = storage
        self.pipeline = pipeline
        self.settings = settings
        self.root = Path(settings.storage.local.root)
        # TTL cache for list_entities
        self._list_cache: dict = {}
        self._list_cache_ts: dict = {}
        self._list_cache_ttl: float = 10.0  # seconds

    # ------------------------------------------------------------------
    # Internal: Entity ↔ dict conversion (from manifest or xattr fallback)
    # ------------------------------------------------------------------

    def _assemble_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> Entity | None:
        """Assemble Entity from manifest (source of truth) or xattr (fallback)."""
        data = self.storage.assemble_entity(workspace_id, collection_id, entity_id)
        if data is None:
            return None
        try:
            return Entity(
                entity_id=data["entity_id"],
                entity_type=data.get("entity_type", "document"),
                workspace_id=data.get("workspace_id", workspace_id),
                collection_id=data.get("collection_id", collection_id),
                name=data.get("name", entity_id),
                source_type=SourceType(data.get("source_type", "oss")),
                source_uri=data.get("source_uri", ""),
                content_hash=data.get("content_hash", ""),
                version=data.get("version", 1),
                status=EntityStatus(data.get("status", "enabled")),
                labels=data.get("labels", []),
                created_at=data.get("created_at") or datetime.now(),
                updated_at=data.get("updated_at") or datetime.now(),
            )
        except Exception as e:
            logger.warning("Failed to assemble entity %s: %s", entity_id, e)
            return None

    def _write_entity_meta(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        entity: Entity,
    ) -> None:
        """Write manifest (source of truth) then sync xattr tags (best-effort cache).

        Write order: manifest first (fsync), then tags (best-effort).
        The manifest stores the COMPLETE entity state.
        """
        # 1. Manifest (source of truth) — ALL entity fields
        self.storage.save_entity_manifest(
            workspace_id, collection_id, entity_id,
            {
                "entity_id": entity.entity_id,
                "workspace_id": entity.workspace_id,
                "collection_id": entity.collection_id,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "source_type": entity.source_type.value,
                "source_uri": entity.source_uri,
                "content_hash": entity.content_hash,
                "version": entity.version,
                "status": entity.status.value,
                "labels": entity.labels,
                "model_version": "embedding-v5",
                "created_at": str(entity.created_at),
                "updated_at": str(entity.updated_at),
            },
        )

        # 2. Sync xattr tags from manifest (best-effort cache)
        self.storage.sync_tags_from_manifest(workspace_id, collection_id, entity_id)

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------

    def _invalidate_list_cache(self, workspace_id: str, collection_id: str) -> None:
        """Invalidate list cache entries for a given workspace/collection."""
        prefix = f"{workspace_id}/{collection_id}/"
        keys_to_remove = [k for k in self._list_cache if k.startswith(prefix)]
        for k in keys_to_remove:
            self._list_cache.pop(k, None)
            self._list_cache_ts.pop(k, None)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_from_file(
        self,
        workspace_id: str,
        collection_id: str,
        file: UploadFile,
    ) -> Entity:
        """Create entity from an uploaded file (only .md supported in v0.1)."""
        filename = file.filename or "unknown.md"
        content = await file.read()
        return await self.create_from_bytes(workspace_id, collection_id, filename, content)

    async def create_from_bytes(
        self,
        workspace_id: str,
        collection_id: str,
        filename: str,
        content: bytes,
    ) -> Entity:
        """Create entity from filename + bytes directly."""
        if not filename.lower().endswith(".md"):
            raise ValueError(f"Unsupported file type: {filename}. Only .md files are supported in v0.1.")

        content_hash = hashlib.sha256(content).hexdigest()[:16]
        entity_id = f"ent_{content_hash}"
        md_content = content.decode("utf-8", errors="replace")

        now = datetime.now()
        entity = Entity(
            entity_id=entity_id,
            entity_type="document",
            workspace_id=workspace_id,
            collection_id=collection_id,
            name=filename,
            source_type=SourceType.OSS,
            source_uri=f"local://{workspace_id}/{collection_id}/{entity_id}/source_original",
            content_hash=content_hash,
            version=1,
            status=EntityStatus.ENABLED,
            created_at=now,
            updated_at=now,
        )

        # Trigger pipeline (saves source_original + canonical_md)
        await self.pipeline.process_md_entity(
            workspace_id, collection_id, entity_id, md_content,
        )

        # Write Entity Tags + manifest AFTER pipeline (source_original must exist)
        self._write_entity_meta(workspace_id, collection_id, entity_id, entity)

        # Set Rep Tags on canonical_md
        self.storage.set_rep_tags(
            workspace_id, collection_id, entity_id, "canonical_md",
            {
                "rep_type": "canonical_md",
                "transform": "parse",
                "pipeline_id": "rep_pipeline_a",
                "pipeline_version": "1",
                "input_content_hash": content_hash,
                "content_hash": content_hash,
                "status": "active",
                "modality": "text",
                "model_version": "",
            },
        )

        # Set Rep Tags on source_original
        self.storage.set_rep_tags(
            workspace_id, collection_id, entity_id, "source_original",
            {
                "rep_type": "source_original",
                "transform": "upload",
                "pipeline_id": "",
                "pipeline_version": "",
                "input_content_hash": "",
                "content_hash": content_hash,
                "status": "active",
                "modality": "text",
                "model_version": "",
            },
        )

        logger.info("Created entity %s from file %s", entity_id, filename)
        self._invalidate_list_cache(workspace_id, collection_id)
        return entity

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> Entity | None:
        """Get entity by ID — assembled from OSS Tag + path."""
        return self._assemble_entity(workspace_id, collection_id, entity_id)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_entities(
        self,
        workspace_id: str,
        collection_id: str,
        status_filter: str | None = None,
    ) -> list[Entity]:
        """List all entities, optionally filtered by rag_status."""
        cache_key = f"{workspace_id}/{collection_id}/{status_filter or ''}"
        now = time.time()
        if cache_key in self._list_cache and (now - self._list_cache_ts.get(cache_key, 0)) < self._list_cache_ttl:
            return self._list_cache[cache_key]

        entity_ids = self.storage.list_entities(workspace_id, collection_id)
        entities: list[Entity] = []
        for eid in entity_ids:
            entity = self._assemble_entity(workspace_id, collection_id, eid)
            if entity is not None:
                if status_filter and entity.status.value != status_filter:
                    continue
                entities.append(entity)

        self._list_cache[cache_key] = entities
        self._list_cache_ts[cache_key] = now
        return entities

    # ------------------------------------------------------------------
    # Pipeline status
    # ------------------------------------------------------------------

    async def get_pipeline_status(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> PipelineStatus | None:
        """Get the pipeline processing status for an entity."""
        entity = await self.get_entity(workspace_id, collection_id, entity_id)
        if entity is None:
            return None

        entity_dir = self.root / workspace_id / collection_id / entity_id
        if not entity_dir.exists():
            return PipelineStatus(
                entity_id=entity_id,
                entity_status=entity.status.value,
                pipeline_stage="pending",
            )

        # Check each known rep
        reps: list[RepInfo] = []
        for rep_type in KNOWN_REP_TYPES:
            rep_path = entity_dir / rep_type
            if rep_path.exists():
                rep_tags = self.storage.get_rep_tags(workspace_id, collection_id, entity_id, rep_type)
                reps.append(RepInfo(
                    rep_type=rep_type,
                    exists=True,
                    size=rep_path.stat().st_size,
                    content_hash=rep_tags.get("content_hash", ""),
                ))
            else:
                reps.append(RepInfo(rep_type=rep_type, exists=False))

        # Extra rep files
        for f in sorted(entity_dir.iterdir()):
            if f.is_file() and f.name not in KNOWN_REP_TYPES and f.name != ".entity_manifest.json":
                rep_tags = self.storage.get_rep_tags(workspace_id, collection_id, entity_id, f.name)
                reps.append(RepInfo(
                    rep_type=f.name,
                    exists=True,
                    size=f.stat().st_size,
                    content_hash=rep_tags.get("content_hash", ""),
                ))

        # Determine pipeline stage
        source_exists = entity_dir.joinpath("source_original").exists()
        canonical_exists = entity_dir.joinpath("canonical_md").exists()

        if source_exists and canonical_exists:
            pipeline_stage = "completed"
        elif source_exists:
            pipeline_stage = "processing"
        else:
            pipeline_stage = "pending"

        # Check index via IndexService (single entry point for LanceDB)
        indexed = False
        chunk_count = 0
        try:
            chunk_count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.pipeline.index.count_entity_chunks(workspace_id, collection_id, entity_id),
            )
            indexed = chunk_count > 0
        except Exception:
            pass

        return PipelineStatus(
            entity_id=entity_id,
            entity_status=entity.status.value,
            reps=reps,
            chunk_count=chunk_count,
            indexed=indexed,
            pipeline_stage=pipeline_stage,
        )

    # ------------------------------------------------------------------
    # Update status (via OSS Tag)
    # ------------------------------------------------------------------

    async def patch_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        status: EntityStatus | None = None,
        labels: list[str] | None = None,
    ) -> Entity | None:
        """Update entity status/labels — writes to OSS Tag + manifest."""
        entity = await self.get_entity(workspace_id, collection_id, entity_id)
        if entity is None:
            return None

        if status is not None:
            entity.status = status
        if labels is not None:
            entity.labels = labels

        entity.updated_at = datetime.now()

        # Update OSS Tags + manifest
        self._write_entity_meta(workspace_id, collection_id, entity_id, entity)

        logger.info("Patched entity %s: status=%s, labels=%s", entity_id, entity.status, entity.labels)
        self._invalidate_list_cache(workspace_id, collection_id)
        return entity

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        hard: bool = False,
    ) -> bool:
        """Delete an entity.

        soft delete (default): set rag_status=deleted via OSS Tag
        hard delete: remove storage dir + LanceDB index entries
        """
        entity = await self.get_entity(workspace_id, collection_id, entity_id)
        if entity is None:
            return False

        if hard:
            entity_dir = self.root / workspace_id / collection_id / entity_id
            if entity_dir.exists():
                shutil.rmtree(entity_dir)
                logger.info("Hard deleted entity %s: removed storage", entity_id)

            try:
                self.pipeline.index.delete_entity_chunks(workspace_id, collection_id, entity_id)
                logger.info("Hard deleted entity %s: removed from index", entity_id)
            except Exception as e:
                logger.warning("Failed to remove entity %s from index: %s", entity_id, e)
        else:
            # Soft delete: update rag_status tag
            entity.status = EntityStatus.DELETED
            entity.updated_at = datetime.now()
            self._write_entity_meta(workspace_id, collection_id, entity_id, entity)
            logger.info("Soft deleted entity %s", entity_id)

        self._invalidate_list_cache(workspace_id, collection_id)
        return True
