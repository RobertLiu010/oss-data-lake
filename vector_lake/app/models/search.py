from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    workspace_id: str = "ws_001"
    collection_id: str = "kb_001"
    # Hybrid search params
    search_type: str = "semantic"  # "semantic" | "lexical" | "hybrid"
    rrf_k: int = 60  # RRF constant (default 60, common range 10-100)
    semantic_weight: float = 0.7  # weight for semantic results in hybrid
    lexical_weight: float = 0.3  # weight for lexical results in hybrid


class SearchResult(BaseModel):
    entity_id: str
    chunk_index: int
    text: str
    score: float
    metadata: dict = {}
    search_type: str = "semantic"  # which search produced this result
