"""S3/MinIO storage backend for Vector Lake.

Implements StorageProtocol using S3-compatible object storage (MinIO, AWS S3, etc.).
Object key layout: {prefix}/{workspace_id}/{collection_id}/{entity_id}/{rep_type_path}
Metadata (entity tags, rep tags, manifest) stored as S3 object metadata.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.storage.lineage import rep_type_to_relpath

logger = logging.getLogger(__name__)


class S3Storage:
    """S3/MinIO-compatible object storage backend.

    Implements StorageProtocol — see app.storage.protocol for the contract.

    Object layout:
        {prefix}/{ws}/{col}/{entity_id}/source/original
        {prefix}/{ws}/{col}/{entity_id}/extract/canonical.md
        {prefix}/{ws}/{col}/{entity_id}/.entity_manifest.json
        {prefix}/{ws}/{col}/{entity_id}/.version_log.jsonl

    Tags (entity + rep) are stored as S3 object metadata (user-defined).
    Manifest is stored as a separate JSON object.
    """

    def __init__(self, settings: Settings):
        s3_cfg = settings.storage.s3
        self._endpoint_url = s3_cfg.endpoint_url
        self._access_key = s3_cfg.access_key
        self._secret_key = s3_cfg.secret_key
        self._bucket = s3_cfg.bucket
        self._prefix = s3_cfg.prefix.rstrip("/")
        self._region = s3_cfg.region

        # Lazy init boto3 client
        self._client = None
        self._ensure_bucket()

    @property
    def root(self) -> Path:
        """Return a pseudo-root for compatibility with StorageProtocol.root."""
        return Path(f"s3://{self._bucket}/{self._prefix}")

    def _get_client(self):
        """Lazy-init boto3 S3 client."""
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint_url,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
                region_name=self._region,
            )
        return self._client

    def _ensure_bucket(self):
        """Create bucket if it doesn't exist."""
        client = self._get_client()
        try:
            client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                client.create_bucket(Bucket=self._bucket)
                logger.info("Created S3 bucket: %s", self._bucket)
            except Exception as e:
                logger.warning("Failed to create bucket %s: %s", self._bucket, e)

    def _object_key(self, workspace_id: str, collection_id: str, entity_id: str, rep_type: str) -> str:
        """Build S3 object key for a rep file."""
        relpath = rep_type_to_relpath(rep_type)
        return f"{self._prefix}/{workspace_id}/{collection_id}/{entity_id}/{relpath}"

    def _manifest_key(self, workspace_id: str, collection_id: str, entity_id: str) -> str:
        return f"{self._prefix}/{workspace_id}/{collection_id}/{entity_id}/.entity_manifest.json"

    def _version_log_key(self, workspace_id: str, collection_id: str, entity_id: str) -> str:
        return f"{self._prefix}/{workspace_id}/{collection_id}/{entity_id}/.version_log.jsonl"

    def _entity_prefix(self, workspace_id: str, collection_id: str, entity_id: str) -> str:
        return f"{self._prefix}/{workspace_id}/{collection_id}/{entity_id}/"

    def _collection_prefix(self, workspace_id: str, collection_id: str) -> str:
        return f"{self._prefix}/{workspace_id}/{collection_id}/"

    def _workspace_prefix(self, workspace_id: str) -> str:
        return f"{self._prefix}/{workspace_id}/"

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def save_file(self, workspace_id: str, collection_id: str, entity_id: str, rep_type: str, content: bytes) -> str:
        key = self._object_key(workspace_id, collection_id, entity_id, rep_type)
        client = self._get_client()
        client.put_object(Bucket=self._bucket, Key=key, Body=content)
        return f"s3://{self._bucket}/{key}"

    def read_file(self, workspace_id: str, collection_id: str, entity_id: str, rep_type: str) -> bytes | None:
        key = self._object_key(workspace_id, collection_id, entity_id, rep_type)
        client = self._get_client()
        try:
            resp = client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception:
            return None

    def file_exists(self, workspace_id: str, collection_id: str, entity_id: str, rep_type: str) -> bool:
        key = self._object_key(workspace_id, collection_id, entity_id, rep_type)
        client = self._get_client()
        try:
            client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def list_entities(self, workspace_id: str, collection_id: str) -> list[str]:
        """List entity IDs by listing common prefixes under the collection prefix."""
        prefix = self._collection_prefix(workspace_id, collection_id)
        client = self._get_client()
        entity_ids = set()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                # prefix like "data/ws/col/entity_id/"
                parts = cp["Prefix"].rstrip("/").split("/")
                if len(parts) >= 1:
                    eid = parts[-1]
                    if not eid.startswith("_"):
                        entity_ids.add(eid)
        return sorted(entity_ids)

    # ------------------------------------------------------------------
    # Entity Tags (stored as S3 object metadata on source_original)
    # ------------------------------------------------------------------

    def set_entity_tags(self, workspace_id: str, collection_id: str, entity_id: str, tags: dict[str, str]) -> None:
        """Store entity tags as S3 object metadata on source_original."""
        key = self._object_key(workspace_id, collection_id, entity_id, "source_original")
        client = self._get_client()
        try:
            # Read existing content first
            try:
                resp = client.get_object(Bucket=self._bucket, Key=key)
                content = resp["Body"].read()
            except Exception:
                return  # source_original doesn't exist

            # Build metadata dict (S3 metadata keys must be lowercase, no special chars)
            metadata = {}
            for k, v in tags.items():
                metadata[f"vl_{k}"] = v

            # Copy object with updated metadata
            client.copy_object(
                Bucket=self._bucket,
                Key=key,
                CopySource={"Bucket": self._bucket, "Key": key},
                Metadata=metadata,
                MetadataDirective="REPLACE",
            )
        except Exception as e:
            logger.warning("Failed to set entity tags for %s: %s", entity_id, e)

    def get_entity_tags(self, workspace_id: str, collection_id: str, entity_id: str) -> dict[str, str]:
        """Get entity tags from S3 object metadata on source_original."""
        key = self._object_key(workspace_id, collection_id, entity_id, "source_original")
        client = self._get_client()
        try:
            resp = client.head_object(Bucket=self._bucket, Key=key)
            metadata = resp.get("Metadata", {})
            tags = {}
            for k, v in metadata.items():
                if k.startswith("vl_"):
                    tags[k[3:]] = v  # strip "vl_" prefix
            return tags
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Representation Tags
    # ------------------------------------------------------------------

    def set_rep_tags(self, workspace_id: str, collection_id: str, entity_id: str, rep_type: str, tags: dict[str, str]) -> None:
        """Store rep tags as S3 object metadata."""
        key = self._object_key(workspace_id, collection_id, entity_id, rep_type)
        client = self._get_client()
        try:
            try:
                resp = client.get_object(Bucket=self._bucket, Key=key)
                content = resp["Body"].read()
            except Exception:
                return

            metadata = {}
            for k, v in tags.items():
                metadata[f"vl_{k}"] = v

            client.copy_object(
                Bucket=self._bucket,
                Key=key,
                CopySource={"Bucket": self._bucket, "Key": key},
                Metadata=metadata,
                MetadataDirective="REPLACE",
            )
        except Exception as e:
            logger.warning("Failed to set rep tags for %s/%s: %s", entity_id, rep_type, e)

    def get_rep_tags(self, workspace_id: str, collection_id: str, entity_id: str, rep_type: str) -> dict[str, str]:
        """Get rep tags from S3 object metadata."""
        key = self._object_key(workspace_id, collection_id, entity_id, rep_type)
        client = self._get_client()
        try:
            resp = client.head_object(Bucket=self._bucket, Key=key)
            metadata = resp.get("Metadata", {})
            tags = {}
            for k, v in metadata.items():
                if k.startswith("vl_"):
                    tags[k[3:]] = v
            return tags
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Entity Manifest (single source of truth)
    # ------------------------------------------------------------------

    def save_entity_manifest(self, workspace_id: str, collection_id: str, entity_id: str, manifest: dict) -> None:
        key = self._manifest_key(workspace_id, collection_id, entity_id)
        client = self._get_client()
        data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType="application/json")

    def read_entity_manifest(self, workspace_id: str, collection_id: str, entity_id: str) -> dict | None:
        key = self._manifest_key(workspace_id, collection_id, entity_id)
        client = self._get_client()
        try:
            resp = client.get_object(Bucket=self._bucket, Key=key)
            data = resp["Body"].read().decode("utf-8")
            return json.loads(data)
        except Exception:
            return None

    def sync_tags_from_manifest(self, workspace_id: str, collection_id: str, entity_id: str) -> None:
        """Read manifest and sync tags to S3 object metadata."""
        manifest = self.read_entity_manifest(workspace_id, collection_id, entity_id)
        if not manifest:
            return
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
            logger.warning("Failed to sync tags for %s (non-fatal): %s", entity_id, e)

    # ------------------------------------------------------------------
    # Version log
    # ------------------------------------------------------------------

    def append_version_log(self, workspace_id: str, collection_id: str, entity_id: str, version: int, content_hash: str, trigger: str = "update") -> None:
        """Append to version log. For S3, we read-modify-write the log object."""
        key = self._version_log_key(workspace_id, collection_id, entity_id)
        client = self._get_client()
        entry = {
            "version": version,
            "content_hash": content_hash,
            "timestamp": datetime.now().isoformat() + "Z",
            "trigger": trigger,
        }
        # Read existing log
        existing_lines = []
        try:
            resp = client.get_object(Bucket=self._bucket, Key=key)
            existing_data = resp["Body"].read().decode("utf-8")
            existing_lines = existing_data.splitlines()
        except Exception:
            pass  # new log

        existing_lines.append(json.dumps(entry, ensure_ascii=False))
        client.put_object(
            Bucket=self._bucket, Key=key,
            Body="\n".join(existing_lines) + "\n",
            ContentType="application/x-jsonlines",
        )

    def read_version_log(self, workspace_id: str, collection_id: str, entity_id: str) -> list[dict]:
        key = self._version_log_key(workspace_id, collection_id, entity_id)
        client = self._get_client()
        try:
            resp = client.get_object(Bucket=self._bucket, Key=key)
            data = resp["Body"].read().decode("utf-8")
            entries = []
            for line in data.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
            return entries
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Entity assembly
    # ------------------------------------------------------------------

    def assemble_entity(self, workspace_id: str, collection_id: str, entity_id: str) -> dict | None:
        """Assemble Entity attributes from manifest (source of truth)."""
        # Check entity exists by checking for any objects under its prefix
        prefix = self._entity_prefix(workspace_id, collection_id, entity_id)
        client = self._get_client()
        try:
            resp = client.list_objects_v2(Bucket=self._bucket, Prefix=prefix, MaxKeys=1)
            if resp.get("KeyCount", 0) == 0:
                return None
        except Exception:
            return None

        # Try manifest first
        manifest = self.read_entity_manifest(workspace_id, collection_id, entity_id)
        if manifest:
            return {
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

        # Fallback: assemble from tags
        tags = self.get_entity_tags(workspace_id, collection_id, entity_id)
        return {
            "entity_id": entity_id,
            "workspace_id": workspace_id,
            "collection_id": collection_id,
            "entity_type": tags.get("entity_type", "document"),
            "name": tags.get("name", entity_id),
            "source_type": "oss",
            "source_uri": f"s3://{self._bucket}/{self._prefix}/{workspace_id}/{collection_id}/{entity_id}/source_original",
            "content_hash": tags.get("content_hash", ""),
            "version": int(tags.get("version", "1")),
            "status": tags.get("rag_status", "enabled"),
            "labels": tags.get("labels", "").split(",") if tags.get("labels") else [],
            "model_version": tags.get("model_version", ""),
            "created_at": "",
            "updated_at": "",
        }

    # ------------------------------------------------------------------
    # Workspace / Collection management (S3 prefix-based)
    # ------------------------------------------------------------------

    def list_workspaces(self) -> list[str]:
        """List workspace IDs by listing common prefixes under root prefix."""
        prefix = f"{self._prefix}/"
        client = self._get_client()
        ws_ids = set()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                parts = cp["Prefix"].rstrip("/").split("/")
                if parts:
                    ws_ids.add(parts[-1])
        return sorted(ws_ids)

    def list_collections(self, workspace_id: str) -> list[str]:
        """List collection IDs under a workspace."""
        prefix = self._workspace_prefix(workspace_id)
        client = self._get_client()
        col_ids = set()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                parts = cp["Prefix"].rstrip("/").split("/")
                if parts:
                    col_ids.add(parts[-1])
        return sorted(col_ids)

    def create_workspace(self, workspace_id: str) -> None:
        """Create workspace by writing a sentinel object."""
        key = f"{self._prefix}/{workspace_id}/.workspace"
        client = self._get_client()
        client.put_object(Bucket=self._bucket, Key=key, Body=b"")

    def create_collection(self, workspace_id: str, collection_id: str) -> None:
        """Create collection by writing a sentinel object."""
        key = f"{self._prefix}/{workspace_id}/{collection_id}/.collection"
        client = self._get_client()
        client.put_object(Bucket=self._bucket, Key=key, Body=b"")

    def delete_workspace(self, workspace_id: str) -> None:
        """Delete all objects under workspace prefix."""
        prefix = self._workspace_prefix(workspace_id)
        self._delete_prefix(prefix)

    def delete_collection(self, workspace_id: str, collection_id: str) -> None:
        """Delete all objects under collection prefix."""
        prefix = self._collection_prefix(workspace_id, collection_id)
        self._delete_prefix(prefix)

    def _delete_prefix(self, prefix: str) -> None:
        """Delete all objects under a given prefix."""
        client = self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if objects:
                delete_keys = [{"Key": obj["Key"]} for obj in objects]
                client.delete_objects(Bucket=self._bucket, Delete={"Objects": delete_keys})

    def entity_dir_exists(self, workspace_id: str, collection_id: str, entity_id: str) -> bool:
        """Check if any objects exist under the entity prefix."""
        prefix = self._entity_prefix(workspace_id, collection_id, entity_id)
        client = self._get_client()
        try:
            resp = client.list_objects_v2(Bucket=self._bucket, Prefix=prefix, MaxKeys=1)
            return resp.get("KeyCount", 0) > 0
        except Exception:
            return False
