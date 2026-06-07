"""Lineage-based directory hierarchy for Vector-Lake representations.

Implements PRD §4.2 — representations are stored in a directory hierarchy
that encodes lineage depth:

    {entity_id}/
    ├── source/original          ← L0 (raw, immutable)
    ├── extract/canonical.md     ← L1 (direct extraction from source)
    ├── extract/layout.json      ← L1
    ├── extract/page_image/      ← L1 (multi-file rep)
    ├── recognize/vlm.md         ← L2 (recognition from extract)
    ├── recognize/transcript.md  ← L2
    ├── compile/graph.json       ← L3 (compilation from extract/recognize)
    ├── compile/summary.md       ← L3
    └── _index/                  ← system directory (index + staging)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Lineage stages and their depth levels
# ---------------------------------------------------------------------------

LINEAGE_STAGES: dict[str, int] = {
    "source": 0,
    "extract": 1,
    "recognize": 2,
    "compile": 3,
}

# ---------------------------------------------------------------------------
# Mapping from rep_type → (stage, filename)
# ---------------------------------------------------------------------------

REP_TYPE_TO_PATH: dict[str, tuple[str, str]] = {
    "source_original": ("source", "original"),
    "canonical_md": ("extract", "canonical.md"),
    "plain_text": ("extract", "plain_text.txt"),
    "layout_json": ("extract", "layout.json"),
    "page_image": ("extract", "page_image"),
    "vlm_md": ("recognize", "vlm.md"),
    "ocr_text": ("recognize", "ocr.md"),
    "transcript": ("recognize", "transcript.md"),
    "audio_segment": ("recognize", "audio_segment"),
    "graph_json": ("compile", "graph.json"),
    "mind_map": ("compile", "mind_map.json"),
    "summary": ("compile", "summary.md"),
    "wiki_md": ("compile", "wiki.md"),
    "table_md": ("compile", "table.md"),
    "table_json": ("compile", "table.json"),
    "table_parquet": ("compile", "table.parquet"),
}

# ---------------------------------------------------------------------------
# System directories (skipped by VFS content scan)
# ---------------------------------------------------------------------------

SYSTEM_DIRS: set[str] = {"_index"}

# ---------------------------------------------------------------------------
# Reverse lookup cache (built once at import time)
# ---------------------------------------------------------------------------

_RELPATH_TO_REP_TYPE: dict[str, str] = {
    f"{stage}/{filename}": rep_type
    for rep_type, (stage, filename) in REP_TYPE_TO_PATH.items()
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def rep_type_to_relpath(rep_type: str) -> str:
    """Convert a rep_type to its relative path within the entity directory.

    For unknown rep_types, defaults to ``extract/{rep_type}`` (L1).
    """
    entry = REP_TYPE_TO_PATH.get(rep_type)
    if entry is not None:
        stage, filename = entry
        return f"{stage}/{filename}"
    return f"extract/{rep_type}"


def relpath_to_rep_type(relpath: str) -> str:
    """Convert a relative path back to its rep_type.

    For unknown paths, uses the filename stem (without extension) as the
    rep_type.
    """
    rep_type = _RELPATH_TO_REP_TYPE.get(relpath)
    if rep_type is not None:
        return rep_type
    # Fallback: use the filename stem (e.g. "extract/foo.md" → "foo")
    filename = relpath.rsplit("/", 1)[-1]
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return stem


def get_lineage_depth(rep_type: str) -> int:
    """Return the lineage depth (0–3) for a rep_type."""
    entry = REP_TYPE_TO_PATH.get(rep_type)
    if entry is not None:
        stage, _ = entry
        return LINEAGE_STAGES[stage]
    # Unknown rep_types default to L1 (extract)
    return 1


def get_stage(rep_type: str) -> str:
    """Return the stage name for a rep_type.

    One of: "source", "extract", "recognize", "compile".
    """
    entry = REP_TYPE_TO_PATH.get(rep_type)
    if entry is not None:
        return entry[0]
    return "extract"


# ---------------------------------------------------------------------------
# Modality mapping
# ---------------------------------------------------------------------------

REP_TYPE_MODALITY: dict[str, str] = {
    "source_original": "text",
    "canonical_md": "text",
    "plain_text": "text",
    "layout_json": "text",
    "page_image": "image",
    "vlm_md": "text",
    "ocr_text": "text",
    "transcript": "text",
    "audio_segment": "audio",
    "graph_json": "text",
    "mind_map": "text",
    "summary": "text",
    "wiki_md": "text",
    "table_md": "table",
    "table_json": "table",
    "table_parquet": "table",
}


def get_modality(rep_type: str) -> str:
    """Return the modality for a given rep_type.

    One of: "text", "image", "audio", "video", "table".
    Defaults to "text" for unknown rep_types.
    """
    return REP_TYPE_MODALITY.get(rep_type, "text")
