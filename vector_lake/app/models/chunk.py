"""Chunk model with layout and anchor support (PRD §4.3.1).

Chunk is the fundamental unit of indexing. Each chunk carries:
- Text content + embedding text
- Position info (start_pos, end_pos)
- Layout info (page_number, blocks, bbox) — from layout_json alignment
- Anchor info — for jump-to-source navigation
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LayoutBlock(BaseModel):
    """A single layout block from layout_json (PRD §4.3.1).

    Represents a structural element (heading, paragraph, table, image, etc.)
    with position info for anchor-jump navigation.
    """

    block_id: str = Field(default="", description="Unique block identifier for cross-Rep anchoring")
    type: str = Field(
        default="paragraph",
        description="Block type: heading/paragraph/table/image/list/code/blockquote/page_break",
    )
    text: str = Field(default="", description="Block text content")
    level: int = Field(default=0, description="Heading level (1-6) for heading blocks")
    bbox: list[float] = Field(default_factory=list, description="Bounding box [x1, y1, x2, y2] in page coordinates")
    start_pos: int = Field(default=0, description="Start character offset in canonical_md")
    end_pos: int = Field(default=0, description="End character offset in canonical_md")
    page_number: int = Field(default=0, description="Page number (1-based)")
    # Optional fields for specific block types
    image_ref: str = Field(default="", description="Reference to page_image file (for image blocks)")
    caption: str = Field(default="", description="Caption text (for image/table blocks)")
    language: str = Field(default="", description="Code language (for code blocks)")
    list_type: str = Field(default="", description="List type: ordered/unordered (for list blocks)")
    table_meta: dict[str, Any] = Field(default_factory=dict, description="Table metadata: rows/cols (for table blocks)")


class ChunkLayout(BaseModel):
    """Layout information for a chunk, mapped from layout_json (PRD §4.3.1).

    Contains the subset of layout blocks that overlap with the chunk's
    character range [start_pos, end_pos), plus page dimensions.
    """

    blocks: list[LayoutBlock] = Field(default_factory=list, description="Layout blocks overlapping this chunk")
    page_number: int = Field(default=0, description="Primary page number (from first block)")
    page_width: float = Field(default=0, description="Page width in points")
    page_height: float = Field(default=0, description="Page height in points")
    source_rep: str = Field(default="canonical_md", description="Source representation this layout was mapped from")
    layout_version: int = Field(default=1, description="layout_json version")


class ChunkAnchor(BaseModel):
    """Anchor for jump-to-source navigation (PRD §4.3.1).

    Supports 5 anchor types:
    - Markdown slug (from heading text)
    - Page number (for PDF/image docs)
    - BBox coordinates (for visual positioning)
    - Character offset (start_pos in canonical_md)
    - Timestamp (for audio/video, future)
    """

    slug: str = Field(default="", description="Markdown heading slug (e.g. 'q3-pricing')")
    page_number: int = Field(default=0, description="Page number anchor (1-based)")
    bbox: list[float] = Field(default_factory=list, description="Bounding box anchor [x1, y1, x2, y2]")
    char_offset: int = Field(default=0, description="Character offset in source rep")
    timestamp: float = Field(default=0, description="Timestamp in seconds (for audio/video)")


class Chunk(BaseModel):
    """A chunk of text produced by the chunking service.

    Core fields:
    - text: the chunk's raw text
    - embedding_text: the text used for embedding (may include sliding window context)
    - start_pos / end_pos: character range in the source text

    Layout fields (PRD §4.3.1):
    - layout:排版信息 mapped from layout_json
    - anchor: 锚点信息 for jump-to-source
    """

    text: str = Field(description="Chunk raw text")
    embedding_text: str = Field(default="", description="Text used for vectorization (may include window context)")
    start_pos: int = Field(default=0, description="Start character offset in source text")
    end_pos: int = Field(default=0, description="End character offset in source text")
    token_count: int = Field(default=0, description="Estimated token count")
    chunk_chars: int = Field(default=0, description="Character count of chunk text")
    layout: ChunkLayout | None = Field(default=None, description="Layout info from layout_json alignment")
    anchor: ChunkAnchor | None = Field(default=None, description="Anchor for jump-to-source navigation")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
