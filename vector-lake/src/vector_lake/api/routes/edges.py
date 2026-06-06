"""Edge API routes (§14)."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from vector_lake.models.edge import Edge

router = APIRouter(prefix="/v1", tags=["edges"])


class CreateEdgeRequest(BaseModel):
    src_entity_id: str
    dst_entity_id: str
    relation: str = Field(description="Edge type: cites/mentions/same_as/depends_on/...")
    weight: float = Field(default=1.0)
    provenance: str = Field(default="manual")


@router.post("/edges", status_code=201)
async def create_edge(req: CreateEdgeRequest) -> Edge:
    """Create an edge (§5.11)."""
    # TODO: delegate to EdgeService
    raise NotImplementedError


@router.get("/edges")
async def list_edges(
    entity_id: str = Query(...),
    relation: str = Query(default=""),
    direction: str = Query(default="both", description="outgoing/incoming/both"),
    limit: int = Query(default=50),
) -> list[Edge]:
    """List edges for an entity."""
    # TODO: delegate to EdgeService
    return []


@router.delete("/edges/{edge_id}")
async def delete_edge(edge_id: str) -> dict[str, str]:
    """Delete an edge."""
    # TODO: delegate to EdgeService
    return {"status": "deleted", "edge_id": edge_id}
