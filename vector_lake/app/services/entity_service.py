"""Entity business logic.

Entity attributes assembled from OSS Tag + path (PRD §4.1):
- Entity Tag (7 keys) on source_original: rag_status, entity_type, name, content_hash, version, labels, model_version
- workspace_id / collection_id / entity_id from path
- .entity_manifest.json sidecar for non-derivable info (source_type, source_uri, timestamps)
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

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

    # ------------------------------------------------------------------
    # Internal: Entity ↔ dict conversion (from OSS Tag + path)
    # ------------------------------------------------------------------

    def _assemble_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> Optional[Entity]:
        """Assemble Entity from OSS Tag + path + manifest."""
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
        """Write Entity Tags (xattr) + manifest (sidecar)."""
        # Entity Tags on source_original
        self.storage.set_entity_tags(
            workspace_id, collection_id, entity_id,
            {
                "rag_status": entity.status.value,
                "entity_type": entity.entity_type,
                "name": entity.name,
                "content_hash": entity.content_hash,
                "version": str(entity.version),
                "labels": ",".join(entity.labels),
                "model_version": "embedding-v5",
            },
        )

        # Manifest sidecar (non-derivable info)
        self.storage.save_entity_manifest(
            workspace_id, collection_id, entity_id,
            {
                "source_type": entity.source_type.value,
                "source_uri": entity.source_uri,
                "created_at": str(entity.created_at),
                "updated_at": str(entity.updated_at),
            },
        )

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
        return entity

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> Optional[Entity]:
        """Get entity by ID — assembled from OSS Tag + path."""
        return self._assemble_entity(workspace_id, collection_id, entity_id)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_entities(
        self,
        workspace_id: str,
        collection_id: str,
        status_filter: Optional[str] = None,
    ) -> list[Entity]:
        """List all entities, optionally filtered by rag_status."""
        entity_ids = self.storage.list_entities(workspace_id, collection_id)
        entities: list[Entity] = []
        for eid in entity_ids:
            entity = self._assemble_entity(workspace_id, collection_id, eid)
            if entity is not None:
                if status_filter and entity.status.value != status_filter:
                    continue
                entities.append(entity)
        return entities

    # ------------------------------------------------------------------
    # Pipeline status
    # ------------------------------------------------------------------

    async def get_pipeline_status(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> Optional[PipelineStatus]:
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

        # Check index
        indexed = False
        chunk_count = 0
        try:
            import lancedb
            lance_dir = self.settings.lance.data_dir
            db = lancedb.connect(lance_dir)
            table_name = f"{workspace_id}_{collection_id}_chunks"
            if table_name in db.table_names():
                tbl = db.open_table(table_name)
                df = tbl.to_pandas()
                entity_chunks = df[df["metadata"].apply(
                    lambda m: m.get("entity_id") == entity_id if isinstance(m, dict) else False
                )]
                chunk_count = len(entity_chunks)
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
        status: Optional[EntityStatus] = None,
        labels: Optional[list[str]] = None,
    ) -> Optional[Entity]:
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
                import lancedb
                lance_dir = self.settings.lance.data_dir
                db = lancedb.connect(lance_dir)
                table_name = f"{workspace_id}_{collection_id}_chunks"
                if table_name in db.table_names():
                    tbl = db.open_table(table_name)
                    tbl.delete(f"metadata.entity_id = '{entity_id}'")
                    logger.info("Hard deleted entity %s: removed from index", entity_id)
            except Exception as e:
                logger.warning("Failed to remove entity %s from index: %s", entity_id, e)
        else:
            # Soft delete: update rag_status tag
            entity.status = EntityStatus.DELETED
            entity.updated_at = datetime.now()
            self._write_entity_meta(workspace_id, collection_id, entity_id, entity)
            logger.info("Soft deleted entity %s", entity_id)

        return True
