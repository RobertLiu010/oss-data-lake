"""Representation data models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import Modality, RepStage, RepStatus


class RepresentationTag(BaseModel):
    """OSS Object Tag for Representation (7 fields, §4.6)."""

    rep_type: str = Field(description="Representation type (e.g., canonical_md, page_image)")
    pipeline_id: str = Field(description="Pipeline that produced this rep")
    transform: str = Field(description="Specific transform method")
    modality: str = Field(description="Data modality: text/image/audio/table/graph/wiki")
    status: str = Field(
        default="ready", description="Rep status: ready/skipped/failed/stale/deleted"
    )
    model_version: str = Field(default="", description="Model version that produced this rep")
    entity_version: str = Field(
        default="1", description="Entity version when this rep was produced"
    )


# Standard rep_type → path mapping (§4.2)
REP_TYPE_PATHS: dict[str, tuple[str, str]] = {
    # rep_type → (stage, filename)
    "raw": ("source", "original"),
    "canonical_md": ("extract", "canonical.md"),
    "plain_text": ("extract", "plain_text.txt"),
    "layout_json": ("extract", "layout.json"),
    "page_image": ("extract", "page_image"),  # directory
    "ocr_text": ("recognize", "ocr.md"),
    "vlm_md": ("recognize", "vlm_extracted.md"),
    "caption": ("recognize", "caption.md"),
    "transcript": ("recognize", "transcript.md"),
    "audio_segment": ("recognize", "audio_segment"),  # directory
    "table_md": ("compile", "table.md"),
    "table_json": ("compile", "table.json"),
    "table_parquet": ("compile", "table.parquet"),
    "mind_map": ("compile", "mind_map.json"),
    "wiki_md": ("compile", "wiki.md"),
    "graph_json": ("compile", "graph.json"),
    "summary": ("compile", "summary.md"),
}


class Representation(BaseModel):
    """Representation model (§4.2): Entity's cognitive perspective."""

    entity_id: str
    rep_type: str
    stage: RepStage
    pipeline_id: str = ""
    transform: str = ""
    modality: Modality = Modality.TEXT
    status: RepStatus = RepStatus.READY
    model_version: str = ""
    entity_version: int = 1
    content_hash: str = ""
    oss_uri: str = ""

    def oss_path(self, workspace_id: str, collection_id: str) -> str:
        """Full OSS path for this representation."""
        stage_dir, filename = REP_TYPE_PATHS.get(self.rep_type, (self.stage.value, self.rep_type))
        return f"vector-lake/{workspace_id}/{collection_id}/{self.entity_id}/{stage_dir}/{filename}"

    @classmethod
    def from_tag(cls, entity_id: str, tag: RepresentationTag, oss_uri: str = "") -> Representation:
        """Create Representation from OSS Tag."""
        stage_str, _ = REP_TYPE_PATHS.get(tag.rep_type, ("extract", tag.rep_type))
        return cls(
            entity_id=entity_id,
            rep_type=tag.rep_type,
            stage=RepStage(stage_str),
            pipeline_id=tag.pipeline_id,
            transform=tag.transform,
            modality=Modality(tag.modality),
            status=RepStatus(tag.status),
            model_version=tag.model_version,
            entity_version=int(tag.entity_version),
            oss_uri=oss_uri,
        )
