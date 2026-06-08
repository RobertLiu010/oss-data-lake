from __future__ import annotations

from pathlib import Path
from typing import Any

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


class S3StorageConfig(BaseModel):
    endpoint_url: str = "http://127.0.0.1:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "vector-lake"
    prefix: str = "data"
    region: str = "us-east-1"


class StorageConfig(BaseModel):
    backend: str = "local"
    local: LocalStorageConfig = Field(default_factory=LocalStorageConfig)
    s3: S3StorageConfig = Field(default_factory=S3StorageConfig)


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
    api_keys: dict[str, str] = Field(default_factory=dict)


class VfsConfig(BaseModel):
    cache_ttl: float = 30.0


class RateLimitConfig(BaseModel):
    enabled: bool = True
    default_limit: str = "60/minute"  # slowapi format


class MetricsConfig(BaseModel):
    enabled: bool = True
    path: str = "/metrics"


class CorsConfig(BaseModel):
    origins: str = "*"  # comma-separated, or "*" for all


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
    vfs: VfsConfig = Field(default_factory=VfsConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    cors: CorsConfig = Field(default_factory=CorsConfig)

    model_config = {"extra": "ignore"}


def load_settings(config_path: str | None = None) -> Settings:
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
        with open(config_path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return Settings(**data)

    return Settings()
