"""Edge data models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import EdgeStatus


class Edge(BaseModel):
    """Edge model (§4.4): cross-Entity relationship for graph retrieval."""

    src_entity_id: str
    dst_entity_id: str
    relation: str = Field(description="Edge type: cites/mentions/same_as/depends_on/...")
    status: EdgeStatus = Field(default=EdgeStatus.ACTIVE)
    weight: float = Field(default=1.0)
    provenance: str = Field(default="", description="How this edge was derived")
    created_at: str | None = None
