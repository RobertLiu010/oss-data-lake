"""LanceDB table schemas using LanceModel."""

from lancedb.pydantic import LanceModel, Vector


class ChunkRecord(LanceModel):
    """LanceDB table schema for representations.lance (§4.3).

    PK = (entity_id, rep_type, chunk_index)
    """

    entity_id: str
    rep_type: str
    chunk_index: int
    text: str
    embedding_text: str = ""
    vector: Vector(1024)  # Jina V5 default dimension (MRL truncatable)
    start_pos: int = 0
    token_count: int = 0
    chunk_chars: int = 0
    section_header: str = ""
    section_level: int = 0
    anchor: str = ""
    doc_title: str = ""
    page_number: int | None = None
    modality: str = "text"
    entity_version: int = 1
    workspace_id: str = ""
    collection_id: str = ""
