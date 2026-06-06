"""VFS path resolution and lineage inference (§4.2, §2.5)."""

from __future__ import annotations

from dataclasses import dataclass

from vector_lake.models.enums import RepStage
from vector_lake.models.representation import REP_TYPE_PATHS


@dataclass
class VFSPath:
    """Resolved VFS path components."""

    workspace_id: str
    collection_id: str
    entity_id: str
    stage: RepStage
    filename: str

    def to_oss_path(self) -> str:
        """Full OSS path."""
        return (
            f"vector-lake/{self.workspace_id}/{self.collection_id}"
            f"/{self.entity_id}/{self.stage.value}/{self.filename}"
        )

    @property
    def rep_type(self) -> str | None:
        """Infer rep_type from stage + filename."""
        for rep_type, (stage_str, fname) in REP_TYPE_PATHS.items():
            if stage_str == self.stage.value and fname == self.filename:
                return rep_type
        return None


def parse_entity_path(oss_path: str) -> tuple[str, str, str]:
    """Parse OSS path to (workspace_id, collection_id, entity_id).

    Expected format: vector-lake/{workspace}/{collection}/{entity_id}/...
    """
    parts = oss_path.strip("/").split("/")
    if len(parts) < 4 or parts[0] != "vector-lake":
        raise ValueError(f"Invalid Vector-Lake path: {oss_path}")
    return parts[1], parts[2], parts[3]


def resolve_rep_path(workspace_id: str, collection_id: str, entity_id: str, rep_type: str) -> str:
    """Resolve rep_type to full OSS path."""
    if rep_type not in REP_TYPE_PATHS:
        raise ValueError(f"Unknown rep_type: {rep_type}")
    stage, filename = REP_TYPE_PATHS[rep_type]
    return f"vector-lake/{workspace_id}/{collection_id}/{entity_id}/{stage}/{filename}"


def infer_lineage_depth(stage: RepStage) -> int:
    """Lineage depth from directory stage (§4.2)."""
    depths = {
        RepStage.SOURCE: 0,
        RepStage.EXTRACT: 1,
        RepStage.RECOGNIZE: 2,
        RepStage.COMPILE: 3,
    }
    return depths.get(stage, -1)


def infer_upstream_stage(stage: RepStage) -> list[RepStage]:
    """Infer possible upstream stages for lineage traversal."""
    upstream_map = {
        RepStage.EXTRACT: [RepStage.SOURCE],
        RepStage.RECOGNIZE: [RepStage.EXTRACT],
        RepStage.COMPILE: [RepStage.EXTRACT, RepStage.RECOGNIZE],
    }
    return upstream_map.get(stage, [])
