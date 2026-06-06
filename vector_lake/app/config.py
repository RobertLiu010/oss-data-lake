from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Nested configuration models
# ---------------------------------------------------------------------------

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class LocalStorageConfig(BaseModel):
    root: str = "./data"


class StorageConfig(BaseModel):
    backend: str = "local"
    local: LocalStorageConfig = Field(default_factory=LocalStorageConfig)


class LanceConfig(BaseModel):
    data_dir: str = "./lance_data"


class EmbeddingConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8006"
    model: str = "embedding-v5"
    dimension: int = 1024
    task_passage: str = "retrieval.passage"
    task_query: str = "retrieval.query"
    batch_size: int = 64


class ChunkingConfig(BaseModel):
    method: str = "markdown_heading"
    chunk_tokens: int = 256
    window_size: int = 9
    max_window_length: int = 12000
    target_max_length: int = 10000
    max_table_length: int = 3000


class AuthConfig(BaseModel):
    enabled: bool = False
    api_keys: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Top-level Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    lance: LanceConfig = Field(default_factory=LanceConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)

    model_config = {"extra": "ignore"}


def load_settings(config_path: Optional[str] = None) -> Settings:
    """Load settings from a YAML config file, falling back to defaults."""
    if config_path is None:
        # Look for config.yaml next to the project root
        candidates = [
            Path("config.yaml"),
            Path(__file__).resolve().parent.parent / "config.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = str(candidate)
                break

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = yaml.safe_load(f) or {}
        return Settings(**data)

    return Settings()
