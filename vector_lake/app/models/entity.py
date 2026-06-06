from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


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
