"""Entity data models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import EntityStatus, EntityType


class EntityTag(BaseModel):
    """OSS Object Tag for Entity (7 fields, §4.6).

    Stored on the source/original object via OSS PutObjectTagging.
    workspace_id / collection_id / entity_id are derivable from path, not stored in tags.
    """

    entity_type: str = Field(description="Entity type: document/image/audio/video/table/mixed")
    mime_type: str = Field(description="MIME type of the raw object")
    content_hash: str = Field(description="SHA-256 hash of the raw object content")
    language: str = Field(default="unknown", description="Detected language (ISO 639-1)")
    size_bytes: str = Field(description="File size in bytes (stored as string in OSS Tag)")
    rag_status: str = Field(default="enabled", description="User intent: enabled/hidden/deleted")
    entity_version: str = Field(
        default="1", description="Entity version (monotonically increasing)"
    )


class Entity(BaseModel):
    """Entity model (§4.1): 1 OSS Object = 1 Entity."""

    entity_id: str = Field(description="Unique entity identifier")
    workspace_id: str = Field(description="Workspace ID")
    collection_id: str = Field(description="Collection ID")
    entity_type: EntityType = Field(description="Entity type")
    mime_type: str = Field(description="MIME type")
    content_hash: str = Field(description="Content SHA-256 hash")
    language: str = Field(default="unknown")
    size_bytes: int = Field(default=0)
    status: EntityStatus = Field(default=EntityStatus.ENABLED)
    rag_status: str = Field(default="enabled")
    version: int = Field(default=1)
    labels: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def generate_representation(self, pipeline_id: str) -> str:
        """Trigger representation generation (§4.1).

        Entity is a TRIGGER, not an executor. This method only XADDs to Redis Streams.
        Returns the entry_id from Redis Streams.
        """
        # Actual implementation in EntityService - this is the interface
        raise NotImplementedError("Use EntityService.generate_representation() instead")

    def oss_path(self) -> str:
        """Full OSS path for this entity's source."""
        return (
            f"vector-lake/{self.workspace_id}/{self.collection_id}/{self.entity_id}/source/original"
        )

    def base_path(self) -> str:
        """Base OSS path for this entity's directory."""
        return f"vector-lake/{self.workspace_id}/{self.collection_id}/{self.entity_id}"
