from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    OSS = "oss"
    URL = "url"


class EntityStatus(StrEnum):
    ENABLED = "enabled"
    HIDDEN = "hidden"
    DELETED = "deleted"


class Entity(BaseModel):
    entity_id: str
    entity_type: str = "document"
    workspace_id: str = "ws_001"
    collection_id: str = "kb_001"
    name: str
    source_type: SourceType = SourceType.OSS
    source_uri: str = ""
    content_hash: str = ""
    version: int = 1
    status: EntityStatus = EntityStatus.ENABLED
    labels: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class EntityCreate(BaseModel):
    """Request body for creating entity from URL"""
    source_type: SourceType = SourceType.OSS
    source_url: str = ""
    labels: list[str] = Field(default_factory=list)


# --- Pipeline / Rep status models ---

class RepInfo(BaseModel):
    """Single representation status."""
    rep_type: str
    exists: bool
    size: int = 0
    content_hash: str = ""
    # Intermediate product tracking
    index_mode: str | None = None  # None, "text", "lexical", "vision"
    indexed: bool = False  # whether this rep has been indexed
    source_step: str = ""  # which RepStep produced this rep


class PipelineStatus(BaseModel):
    """Entity pipeline processing status."""
    entity_id: str
    entity_status: str
    reps: list[RepInfo] = Field(default_factory=list)
    chunk_count: int = 0
    indexed: bool = False
    pipeline_stage: str = ""  # "pending" | "processing" | "completed" | "failed"


class EntityPatchRequest(BaseModel):
    """Request body for updating entity status/labels."""
    status: EntityStatus | None = None
    labels: list[str] | None = None
