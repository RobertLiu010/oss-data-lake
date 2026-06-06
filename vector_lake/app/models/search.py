from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    workspace_id: str = "ws_001"
    collection_id: str = "kb_001"


class SearchResult(BaseModel):
    entity_id: str
    chunk_index: int
    text: str
    score: float
    metadata: dict = {}
