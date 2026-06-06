"""Entity business logic."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import UploadFile

from app.config import Settings
from app.models.entity import Entity, EntityStatus, SourceType
from app.services.pipeline import PipelineService
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)


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
    ) -> list[Entity]:
        """List all entities in a collection."""
        entity_ids = self.storage.list_entities(workspace_id, collection_id)
        entities: list[Entity] = []
        for eid in entity_ids:
            raw = self.storage.read_file(
                workspace_id, collection_id, eid, "entity_meta",
            )
            if raw is not None:
                try:
                    entities.append(Entity.model_validate_json(raw.decode("utf-8")))
                except Exception:
                    logger.warning("Failed to parse entity meta for %s", eid)
        return entities
