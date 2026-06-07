"""Models for Reconciler and Watch Mode APIs."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# --- Reconciler models ---

class ReconcileResponse(BaseModel):
    """Response from a reconcile run."""
    entities_scanned: int = 0
    drift_count: int = 0
    drifts_repaired: int = 0
    drifts: list[dict] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# --- Watch Mode models ---

class WatchStrategyCreate(BaseModel):
    """Request body for creating a watch strategy."""
    watch_dir: str
    collection_id: str = "kb_001"
    allowed_extensions: list[str] = Field(default_factory=lambda: [".md"])
    entity_id_strategy: str = "filename"
    on_conflict: str = "update"
    recursive: bool = True
    max_file_size_mb: int = 500
    backend: str = "polling"
    scan_interval: int = 10


class WatchStrategyResponse(BaseModel):
    watch_id: str
    workspace_id: str
    collection_id: str
    watch_dir: str
    allowed_extensions: list[str]
    entity_id_strategy: str
    on_conflict: str
    recursive: bool
    max_file_size_mb: int
    backend: str
    scan_interval: int
    status: str
    total_events: int = 0
    total_processed: int = 0
    total_errors: int = 0
    last_scan_at: Optional[str] = None


class DeadLetterResponse(BaseModel):
    entry_id: str
    workspace_id: str
    collection_id: str
    file_path: str
    error: str
    created_at: str
    replayed: bool = False
