from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional


class SourceType(str, Enum):
    OSS = "oss"
    URL = "url"


class EntityStatus(str, Enum):
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
    status: Optional[EntityStatus] = None
    labels: Optional[list[str]] = None
