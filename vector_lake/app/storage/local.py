"""Local filesystem storage with OSS Tag simulation via xattr.

Design (aligned with PRD §4.6):
- Entity metadata stored as xattr on source_original file (simulating OSS Object Tag)
- Entity Tag (7 keys): rag_status, entity_type, name, content_hash, version, labels, model_version
- workspace_id / collection_id / entity_id derived from path (not stored in Tag)
- .entity_manifest.json sidecar for non-derivable info (Ground Truth for disaster recovery)
- Representation Tag (9 keys) on each rep file
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from app.config import Settings

logger = logging.getLogger(__name__)

# xattr prefix for all Vector-Lake tags
XATTR_PREFIX = "user.vl_"

# Entity Tag keys (7 keys, on source_original)
ENTITY_TAG_KEYS = [
    "rag_status",    # enabled / hidden / deleted
    "entity_type",   # document / image / audio / video / table
    "name",          # original filename
    "content_hash",  # sha256 of raw content
    "version",       # entity version
    "labels",        # comma-separated
    "model_version", # embedding model version
]

# Representation Tag keys (9 keys, on each rep file)
REP_TAG_KEYS = [
    "rep_type",
    "transform",           # RepStep name
    "pipeline_id",
    "pipeline_version",
    "input_content_hash",  # upstream content hash
    "content_hash",        # this rep's content hash
    "status",              # active / stale / failed / deleted
    "modality",            # text / image / audio / video / table
    "model_version",
]


class LocalStorage:
    """Local filesystem storage with OSS Tag simulation via xattr."""

    def __init__(self, settings: Settings):
        self.root = settings.storage.local.root
        Path(self.root).mkdir(parents=True, exist_ok=True)

    def _entity_dir(self, workspace_id: str, collection_id: str, entity_id: str) -> Path:
        return Path(self.root) / workspace_id / collection_id / entity_id

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def save_file(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
        content: bytes,
    ) -> str:
        """Save content bytes to {root}/{ws}/{col}/{entity_id}/{rep_type}."""
        entity_dir = self._entity_dir(workspace_id, collection_id, entity_id)
        entity_dir.mkdir(parents=True, exist_ok=True)
        file_path = entity_dir / rep_type
        file_path.write_bytes(content)
        return str(file_path)

    def read_file(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
    ) -> Optional[bytes]:
        """Read bytes from the stored file, or None if not found."""
        file_path = self._entity_dir(workspace_id, collection_id, entity_id) / rep_type
        if file_path.exists():
            return file_path.read_bytes()
        return None

    def file_exists(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
    ) -> bool:
        """Check whether a stored file exists."""
        file_path = self._entity_dir(workspace_id, collection_id, entity_id) / rep_type
        return file_path.exists()

    def list_entities(self, workspace_id: str, collection_id: str) -> list[str]:
        """List entity_ids by scanning the directory."""
        col_dir = Path(self.root) / workspace_id / collection_id
        if not col_dir.exists():
            return []
        return [
            d.name
            for d in sorted(col_dir.iterdir())
            if d.is_dir()
        ]

    # ------------------------------------------------------------------
    # OSS Tag simulation (xattr)
    # ------------------------------------------------------------------

    @staticmethod
    def _xattr_key(tag_key: str) -> str:
        return f"{XATTR_PREFIX}{tag_key}"

    def set_entity_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        tags: dict[str, str],
    ) -> None:
        """Set Entity Tags on source_original file (simulating OSS Object Tag)."""
        file_path = self._entity_dir(workspace_id, collection_id, entity_id) / "source_original"
        if not file_path.exists():
            logger.warning("Cannot set tags: source_original not found for %s", entity_id)
            return
        for key, value in tags.items():
            if key in ENTITY_TAG_KEYS:
                try:
                    os.setxattr(str(file_path), self._xattr_key(key), value.encode("utf-8"))
                except OSError as e:
                    logger.warning("Failed to set xattr %s: %s", key, e)

    def get_entity_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> dict[str, str]:
        """Get Entity Tags from source_original file."""
        file_path = self._entity_dir(workspace_id, collection_id, entity_id) / "source_original"
        if not file_path.exists():
            return {}
        tags = {}
        for key in ENTITY_TAG_KEYS:
            try:
                val = os.getxattr(str(file_path), self._xattr_key(key))
                tags[key] = val.decode("utf-8")
            except OSError:
                pass  # tag not set
        return tags

    def set_rep_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
        tags: dict[str, str],
    ) -> None:
        """Set Representation Tags on a rep file."""
        file_path = self._entity_dir(workspace_id, collection_id, entity_id) / rep_type
        if not file_path.exists():
            return
        for key, value in tags.items():
            if key in REP_TAG_KEYS:
                try:
                    os.setxattr(str(file_path), self._xattr_key(key), value.encode("utf-8"))
                except OSError as e:
                    logger.warning("Failed to set xattr %s on %s: %s", key, rep_type, e)

    def get_rep_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
    ) -> dict[str, str]:
        """Get Representation Tags from a rep file."""
        file_path = self._entity_dir(workspace_id, collection_id, entity_id) / rep_type
        if not file_path.exists():
            return {}
        tags = {}
        for key in REP_TAG_KEYS:
            try:
                val = os.getxattr(str(file_path), self._xattr_key(key))
                tags[key] = val.decode("utf-8")
            except OSError:
                pass
        return tags

    # ------------------------------------------------------------------
    # Entity Manifest (Ground Truth sidecar)
    # ------------------------------------------------------------------

    def save_entity_manifest(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        manifest: dict,
    ) -> None:
        """Save .entity_manifest.json sidecar (Ground Truth for non-derivable info)."""
        entity_dir = self._entity_dir(workspace_id, collection_id, entity_id)
        entity_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = entity_dir / ".entity_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_entity_manifest(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> Optional[dict]:
        """Read .entity_manifest.json sidecar."""
        manifest_path = self._entity_dir(workspace_id, collection_id, entity_id) / ".entity_manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text("utf-8"))
            except Exception:
                return None
        return None

    # ------------------------------------------------------------------
    # Entity assembly from OSS Tag + path (PRD §4.1)
    # ------------------------------------------------------------------

    def assemble_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> Optional[dict]:
        """Assemble Entity attributes from OSS Tag + path (PRD §4.1).

        Returns a dict matching Entity Schema, or None if entity not found.
        """
        entity_dir = self._entity_dir(workspace_id, collection_id, entity_id)
        if not entity_dir.exists():
            return None

        # From path
        result = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
        }

        # From Entity Tags on source_original
        tags = self.get_entity_tags(workspace_id, collection_id, entity_id)
        result["entity_type"] = tags.get("entity_type", "document")
        result["name"] = tags.get("name", entity_id)
        result["source_type"] = "oss"  # default; URL entities set via manifest
        result["content_hash"] = tags.get("content_hash", "")
        result["version"] = int(tags.get("version", "1"))
        result["status"] = tags.get("rag_status", "enabled")
        result["labels"] = tags.get("labels", "").split(",") if tags.get("labels") else []

        # From manifest (non-derivable info)
        manifest = self.read_entity_manifest(workspace_id, collection_id, entity_id)
        if manifest:
            result["source_type"] = manifest.get("source_type", result["source_type"])
            result["source_uri"] = manifest.get("source_uri", "")
            result["created_at"] = manifest.get("created_at", "")
            result["updated_at"] = manifest.get("updated_at", "")
        else:
            result["source_uri"] = f"local://{workspace_id}/{collection_id}/{entity_id}/source_original"
            result["created_at"] = ""
            result["updated_at"] = ""

        return result
