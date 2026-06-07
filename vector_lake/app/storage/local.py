"""Local filesystem storage with OSS Tag simulation via xattr.

Design (aligned with PRD §4.6):
- .entity_manifest.json is the single source of truth for ALL entity fields
- Entity metadata cached as xattr on source_original file (simulating OSS Object Tag)
- Entity Tag (7 keys): rag_status, entity_type, name, content_hash, version, labels, model_version
- workspace_id / collection_id / entity_id derived from path (not stored in Tag)
- Write order: manifest first (fsync), then tags (best-effort cache)
- Representation Tag (9 keys) on each rep file
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

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
    ) -> bytes | None:
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
        """Save .entity_manifest.json sidecar (single source of truth for ALL entity fields).

        The manifest stores the complete entity state. Write order: manifest first (fsync),
        then tags (best-effort cache via sync_tags_from_manifest).
        """
        entity_dir = self._entity_dir(workspace_id, collection_id, entity_id)
        entity_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = entity_dir / ".entity_manifest.json"
        tmp_path = manifest_path.with_suffix(".json.tmp")
        # Write to temp file, fsync, then atomic rename
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        try:
            data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(str(tmp_path), str(manifest_path))

    def read_entity_manifest(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> dict | None:
        """Read .entity_manifest.json sidecar."""
        manifest_path = self._entity_dir(workspace_id, collection_id, entity_id) / ".entity_manifest.json"
        if manifest_path.exists():
            try:
                return json.loads(manifest_path.read_text("utf-8"))
            except Exception:
                return None
        return None

    def sync_tags_from_manifest(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> None:
        """Read manifest and write xattr tags as a best-effort cache.

        Called after every manifest write to keep the xattr tag cache in sync.
        Failures are logged but not raised — tags are cache, not source of truth.
        """
        manifest = self.read_entity_manifest(workspace_id, collection_id, entity_id)
        if not manifest:
            logger.warning("Cannot sync tags: no manifest for %s", entity_id)
            return

        # Map manifest fields to xattr tag keys
        tags = {
            "rag_status": manifest.get("status", "enabled"),
            "entity_type": manifest.get("entity_type", "document"),
            "name": manifest.get("name", entity_id),
            "content_hash": manifest.get("content_hash", ""),
            "version": str(manifest.get("version", 1)),
            "labels": ",".join(manifest.get("labels", [])),
            "model_version": manifest.get("model_version", ""),
        }
        try:
            self.set_entity_tags(workspace_id, collection_id, entity_id, tags)
        except Exception as e:
            logger.warning("Failed to sync xattr tags for %s (non-fatal): %s", entity_id, e)

    # ------------------------------------------------------------------
    # Entity assembly from manifest (source of truth) or xattr (fallback)
    # ------------------------------------------------------------------

    def assemble_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> dict | None:
        """Assemble Entity attributes from manifest (source of truth) or xattr (fallback cache).

        Read order: manifest first (authoritative), xattr tags only if manifest missing.
        Returns a dict matching Entity Schema, or None if entity not found.
        """
        entity_dir = self._entity_dir(workspace_id, collection_id, entity_id)
        if not entity_dir.exists():
            return None

        # --- Try manifest first (single source of truth) ---
        manifest = self.read_entity_manifest(workspace_id, collection_id, entity_id)
        if manifest:
            # Manifest contains ALL fields; use it directly
            result = {
                "entity_id": manifest.get("entity_id", entity_id),
                "workspace_id": manifest.get("workspace_id", workspace_id),
                "collection_id": manifest.get("collection_id", collection_id),
                "entity_type": manifest.get("entity_type", "document"),
                "name": manifest.get("name", entity_id),
                "source_type": manifest.get("source_type", "oss"),
                "source_uri": manifest.get("source_uri", ""),
                "content_hash": manifest.get("content_hash", ""),
                "version": manifest.get("version", 1),
                "status": manifest.get("status", "enabled"),
                "labels": manifest.get("labels", []),
                "model_version": manifest.get("model_version", ""),
                "created_at": manifest.get("created_at", ""),
                "updated_at": manifest.get("updated_at", ""),
            }
            return result

        # --- Fallback: assemble from xattr tags + path (legacy / no manifest) ---
        logger.info("No manifest for %s, falling back to xattr tags", entity_id)
        result = {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
        }

        tags = self.get_entity_tags(workspace_id, collection_id, entity_id)
        result["entity_type"] = tags.get("entity_type", "document")
        result["name"] = tags.get("name", entity_id)
        result["source_type"] = "oss"
        result["source_uri"] = f"local://{workspace_id}/{collection_id}/{entity_id}/source_original"
        result["content_hash"] = tags.get("content_hash", "")
        result["version"] = int(tags.get("version", "1"))
        result["status"] = tags.get("rag_status", "enabled")
        result["labels"] = tags.get("labels", "").split(",") if tags.get("labels") else []
        result["model_version"] = tags.get("model_version", "")
        result["created_at"] = ""
        result["updated_at"] = ""

        return result
