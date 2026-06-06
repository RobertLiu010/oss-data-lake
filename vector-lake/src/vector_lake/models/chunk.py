"""Chunk data models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import ChunkStatus


class Chunk(BaseModel):
    """Chunk model (§4.3): retrieval granularity within a Representation.

    Identity: (entity_id, rep_type, chunk_index) — no independent chunk_id.
    """

    entity_id: str
    rep_type: str
    chunk_index: int
    text: str = Field(default="", description="Chunk text content")
    embedding_text: str = Field(
        default="", description="Text used for embedding (may differ from text)"
    )
    vector: list[float] = Field(default_factory=list, description="Embedding vector")
    start_pos: int = Field(default=0, description="Start position in source")
    token_count: int = Field(default=0)
    chunk_chars: int = Field(default=0)
    section_header: str = Field(default="")
    section_level: int = Field(default=0)
    anchor: str = Field(default="")
    doc_title: str = Field(default="")
    page_number: int | None = None
    modality: str = Field(default="text")
    status: ChunkStatus = Field(default=ChunkStatus.ACTIVE)
    entity_version: int = Field(default=1)

    @property
    def chunk_id(self) -> str:
        """Unique chunk identifier derived from the identity triple."""
        return f"{self.entity_id}/{self.rep_type}#{self.chunk_index}"

    @property
    def lance_pk(self) -> tuple[str, str, int]:
        """Lance table primary key: (entity_id, rep_type, chunk_index)."""
        return (self.entity_id, self.rep_type, self.chunk_index)
