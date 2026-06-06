"""Pipeline step protocols (§6.6 RepStep, §6.7 IndexStep, §11 ProjectorStep)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import lancedb


@dataclass
class RepStepContext:
    """RepStep execution context, injected by RepPipelineOrchestrator (§6.6.1)."""

    entity_id: str
    entity_type: str
    workspace_id: str
    collection_id: str
    content_hash: str
    entity_version: int
    upstream_outputs: dict[str, RepStepOutput] = field(default_factory=dict)


@dataclass
class RepStepOutput:
    """RepStep output declaration (§6.6.1)."""

    rep_type: str
    stage: str  # source/extract/recognize/compile
    files: dict[str, bytes] = field(default_factory=dict)  # filename → content
    tags: dict[str, str] = field(default_factory=dict)  # OSS Representation Tag


@dataclass
class IndexStepContext:
    """IndexStep execution context, injected by IndexPipelineOrchestrator (§6.7.1)."""

    entity_id: str
    entity_type: str
    workspace_id: str
    collection_id: str
    lance_table: lancedb.db.LanceTable | None = None
    available_reps: dict[str, str] = field(default_factory=dict)  # rep_type → OSS URI


@runtime_checkable
class RepStepProtocol(Protocol):
    """Pluggable content transformation step (§6.6.1)."""

    @property
    def step_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def required_input_reps(self) -> list[str]: ...

    @property
    def optional_input_reps(self) -> list[str]: ...

    @property
    def output_reps(self) -> list[str]: ...

    @property
    def output_stage(self) -> str: ...

    @property
    def supported_entity_types(self) -> list[str]: ...

    @property
    def modality(self) -> str: ...

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Execute step, return output list. Must be idempotent."""
        ...

    def capabilities(self) -> dict[str, bool]:
        return {
            "requires_llm": False,
            "requires_gpu": False,
            "estimated_duration_ms": 1000,
        }


@runtime_checkable
class IndexStepProtocol(Protocol):
    """Pluggable index building step (§6.7.1)."""

    @property
    def step_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def index_type(self) -> str: ...

    @property
    def required_reps(self) -> list[str]: ...

    @property
    def optional_reps(self) -> list[str]: ...

    @property
    def supported_modalities(self) -> list[str]: ...

    def execute(self, ctx: IndexStepContext) -> None:
        """Build index. Must be idempotent."""
        ...

    def is_built(self, ctx: IndexStepContext) -> bool:
        """Check if index already exists."""
        ...

    def rebuild(self, ctx: IndexStepContext) -> None:
        """Delete old index and rebuild."""
        ...

    def capabilities(self) -> dict[str, bool]:
        return {
            "supports_hybrid": False,
            "requires_training": False,
        }


@runtime_checkable
class ProjectorStepProtocol(Protocol):
    """Projector step — special RepStep that projects to external consumers (§11)."""

    @property
    def step_id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def target(self) -> str: ...  # wiki / rag_api / dashboard

    @property
    def required_reps(self) -> list[str]: ...

    def execute(self, ctx: RepStepContext) -> list[RepStepOutput]:
        """Execute projection. Output files go to external target, not back to Lake."""
        ...

    def capabilities(self) -> dict[str, bool]:
        return {
            "requires_llm": False,
            "requires_gpu": False,
        }
