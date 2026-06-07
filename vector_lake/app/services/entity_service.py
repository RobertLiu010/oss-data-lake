"""Entity business logic."""

from __future__ import annotations

import hashlib
import json
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

        # Only .md supported in MVP
        if not filename.lower().endswith(".md"):
            raise ValueError(f"Unsupported file type: {filename}. Only .md files are supported in v0.1.")

        # Generate entity_id from content hash
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        entity_id = f"ent_{content_hash}"

        # Decode content
        md_content = content.decode("utf-8", errors="replace")

        # Create Entity model
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
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Save entity metadata as JSON
        self.storage.save_file(
            workspace_id, collection_id, entity_id,
            "entity_meta", entity.model_dump_json().encode("utf-8"),
        )

        # Trigger pipeline (MD files)
        await self.pipeline.process_md_entity(
            workspace_id, collection_id, entity_id, md_content,
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
        """Get entity by ID."""
        raw = self.storage.read_file(
            workspace_id, collection_id, entity_id, "entity_meta",
        )
        if raw is None:
            return None
        return Entity.model_validate_json(raw.decode("utf-8"))

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_entities(
        self,
        workspace_id: str,
        collection_id: str,
        status_filter: Optional[str] = None,
    ) -> list[Entity]:
        """List all entities in a collection, optionally filtered by status."""
        entity_ids = self.storage.list_entities(workspace_id, collection_id)
        entities: list[Entity] = []
        for eid in entity_ids:
            raw = self.storage.read_file(
                workspace_id, collection_id, eid, "entity_meta",
            )
            if raw is not None:
                try:
                    entity = Entity.model_validate_json(raw.decode("utf-8"))
                    if status_filter and entity.status.value != status_filter:
                        continue
                    entities.append(entity)
                except Exception:
                    logger.warning("Failed to parse entity meta for %s", eid)
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
                reps.append(RepInfo(
                    rep_type=rep_type,
                    exists=True,
                    size=rep_path.stat().st_size,
                    content_hash=hashlib.sha256(rep_path.read_bytes()).hexdigest()[:16],
                ))
            else:
                reps.append(RepInfo(rep_type=rep_type, exists=False))

        # Also check for any extra rep files
        for f in sorted(entity_dir.iterdir()):
            if f.is_file() and f.name not in KNOWN_REP_TYPES and f.name != "entity_meta":
                reps.append(RepInfo(
                    rep_type=f.name,
                    exists=True,
                    size=f.stat().st_size,
                    content_hash=hashlib.sha256(f.read_bytes()).hexdigest()[:16],
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
            from app.services.index import IndexService
            import lancedb
            lance_dir = self.settings.lance.data_dir
            db = lancedb.connect(lance_dir)
            table_name = f"{workspace_id}_{collection_id}_chunks"
            if table_name in db.table_names():
                tbl = db.open_table(table_name)
                # Count chunks for this entity
                import pyarrow.compute as pc
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
    # Update status
    # ------------------------------------------------------------------

    async def patch_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        status: Optional[EntityStatus] = None,
        labels: Optional[list[str]] = None,
    ) -> Optional[Entity]:
        """Update entity status and/or labels."""
        entity = await self.get_entity(workspace_id, collection_id, entity_id)
        if entity is None:
            return None

        if status is not None:
            entity.status = status
        if labels is not None:
            entity.labels = labels

        entity.updated_at = datetime.now()

        # Persist updated meta
        self.storage.save_file(
            workspace_id, collection_id, entity_id,
            "entity_meta", entity.model_dump_json().encode("utf-8"),
        )

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

        soft delete (default): set status=deleted, keep data
        hard delete: remove storage dir + LanceDB index entries
        """
        entity = await self.get_entity(workspace_id, collection_id, entity_id)
        if entity is None:
            return False

        if hard:
            # Remove storage directory
            entity_dir = self.root / workspace_id / collection_id / entity_id
            if entity_dir.exists():
                shutil.rmtree(entity_dir)
                logger.info("Hard deleted entity %s: removed storage", entity_id)

            # Remove from LanceDB index
            try:
                from app.services.index import IndexService
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
            # Soft delete: just update status
            entity.status = EntityStatus.DELETED
            entity.updated_at = datetime.now()
            self.storage.save_file(
                workspace_id, collection_id, entity_id,
                "entity_meta", entity.model_dump_json().encode("utf-8"),
            )
            logger.info("Soft deleted entity %s", entity_id)

        return True
