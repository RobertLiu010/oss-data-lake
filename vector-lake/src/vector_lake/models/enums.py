"""Enumerations for Vector-Lake state model."""

from enum import StrEnum


class EntityStatus(StrEnum):
    """Entity status (§5.2)."""

    ENABLED = "enabled"
    HIDDEN = "hidden"
    DELETED = "deleted"


class RepStatus(StrEnum):
    """Representation status (§5.4)."""

    READY = "ready"
    SKIPPED = "skipped"
    FAILED = "failed"
    STALE = "stale"
    DELETED = "deleted"


class IndexStatus(StrEnum):
    """Index status (§5.10)."""

    BUILT = "built"
    STALE = "stale"
    FAILED = "failed"
    DELETED = "deleted"


class PipelineRunStatus(StrEnum):
    """Pipeline run status (§5.3)."""

    PENDING = "pending"
    RUNNING = "running"
    PARTIAL_SUCCESS = "partial_success"
    SUCCESS = "success"
    FAILED = "failed"


class ChunkStatus(StrEnum):
    """Chunk status (§5.5)."""

    ACTIVE = "active"
    HIDDEN = "hidden"
    DELETED = "deleted"
    STALE = "stale"


class EdgeStatus(StrEnum):
    """Edge status (§5.11)."""

    ACTIVE = "active"
    STALE = "stale"
    DELETED = "deleted"


class Modality(StrEnum):
    """Data modality."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TABLE = "table"
    GRAPH = "graph"
    WIKI = "wiki"


class EntityType(StrEnum):
    """Entity type (6-level classification)."""

    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TABLE = "table"
    MIXED = "mixed"


class RepStage(StrEnum):
    """Representation directory stage (lineage depth)."""

    SOURCE = "source"
    EXTRACT = "extract"
    RECOGNIZE = "recognize"
    COMPILE = "compile"


class IndexType(StrEnum):
    """Index type."""

    SEMANTIC = "semantic"
    LEXICAL = "lexical"
    VISUAL = "visual"
    AUDIO = "audio"
    GRAPH = "graph"
    TABLE = "table"


class TriggerType(StrEnum):
    """Pipeline trigger type."""

    OSS_EVENT = "oss_event"
    RECONCILER = "reconciler"
    MANUAL = "manual"


class MetadataWriteState(StrEnum):
    """Metadata write state machine (§5.12.2)."""

    CLEAN = "clean"
    FILE_WRITTEN = "file_written"
    MANIFEST_WRITTEN = "manifest_written"
    TAG_MISSING = "tag_missing"
