"""Configuration management using Pydantic Settings (§21.4)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageConfig(BaseSettings):
    """OSS / S3 / MinIO connection config."""

    type: str = Field(default="s3", description="s3 | oss | minio")
    endpoint: str = Field(default="http://localhost:9000")
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin")
    bucket: str = Field(default="vector-lake")
    region: str = Field(default="us-east-1")


class LanceDBConfig(BaseSettings):
    """LanceDB config."""

    uri: str = Field(default="s3://vector-lake/lancedb/")
    storage_options: dict[str, str] = Field(default_factory=dict)


class RedisConfig(BaseSettings):
    """Redis connection config."""

    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    password: str = Field(default="")
    stream_maxlen: int = Field(default=100000, description="Backpressure MAXLEN")


class PipelineConfig(BaseSettings):
    """Pipeline execution config."""

    default_concurrency: int = Field(default=4)
    step_timeout: int = Field(default=600, description="RepStep timeout in seconds")
    index_timeout: int = Field(default=300, description="IndexStep timeout in seconds")


class ReconcilerConfig(BaseSettings):
    """Reconciler config."""

    interval: int = Field(default=900, description="Run interval in seconds")
    batch_size: int = Field(default=100)
    phase0_cron: str = Field(default="*/15 * * * *")
    phase1_cron: str = Field(default="0 */2 * * *")
    phase2_cron: str = Field(default="0 */4 * * *")


class MCPConfig(BaseSettings):
    """MCP Server config."""

    enabled: bool = Field(default=True)
    transport: str = Field(default="stdio", description="stdio | sse | http")
    sse_port: int = Field(default=8081)


class ObservabilityConfig(BaseSettings):
    """Observability config."""

    otel_endpoint: str = Field(default="")
    prometheus_port: int = Field(default=9090)
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", description="json | text")


class RetentionConfig(BaseSettings):
    """Data retention config."""

    soft_delete_days: int = Field(default=30)
    cleanup_interval: int = Field(default=86400)


class PluginConfig(BaseSettings):
    """Plugin registration config."""

    rep_steps: list[str] = Field(default_factory=list, description="Extra RepStep module paths")
    index_steps: list[str] = Field(default_factory=list)
    projector_steps: list[str] = Field(default_factory=list)


class VectorLakeConfig(BaseSettings):
    """Root configuration (§21.4)."""

    model_config = SettingsConfigDict(
        env_prefix="VL_",
        env_nested_delimiter="__",
        yaml_file="config.yaml",
    )

    storage: StorageConfig = Field(default_factory=StorageConfig)
    lancedb: LanceDBConfig = Field(default_factory=LanceDBConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    pipelines: PipelineConfig = Field(default_factory=PipelineConfig)
    reconciler: ReconcilerConfig = Field(default_factory=ReconcilerConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    plugins: PluginConfig = Field(default_factory=PluginConfig)
