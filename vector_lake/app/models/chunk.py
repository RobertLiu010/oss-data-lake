from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    text: str = Field(description="中心块原始文本")
    embedding_text: str = Field(default="", description="向量化使用的文本")
    start_pos: int = Field(default=0)
    token_count: int = Field(default=0)
    chunk_chars: int = Field(default=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
