"""OSS/S3/MinIO storage operations for VFS (§4.6, §5.12)."""

from __future__ import annotations

import hashlib
from typing import Any

import boto3
import botocore.config
from botocore.exceptions import ClientError

from vector_lake.config import StorageConfig
from vector_lake.models.entity import EntityTag
from vector_lake.models.enums import MetadataWriteState
from vector_lake.models.representation import RepresentationTag


class ObjectStorage:
    """OSS/S3/MinIO storage backend for Vector-Lake.

    Handles:
    - Object CRUD (get/put/delete/list)
    - Object Tag read/write (Entity Tag 7 fields + Representation Tag 7 fields)
    - ETag-based change detection (Phase 0)
    - Prefix listing with pagination (OSS LIST 1000-object limit)
    - Metadata write state machine (§5.12.2)
    """

    def __init__(self, config: StorageConfig):
        self._config = config
        endpoint_url = config.endpoint if config.type in ("minio", "s3") else None
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=config.access_key,
            aws_secret_access_key=config.secret_key,
            region_name=config.region,
            config=botocore.config.Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
        )
        self._bucket = config.bucket

    async def head_object(self, key: str) -> dict[str, Any]:
        """HeadObject — get metadata without downloading (Phase 0 ETag check).

        Returns dict with: ETag, ContentLength, LastModified, ContentType, etc.
        """
        try:
            resp = self._client.head_object(Bucket=self._bucket, Key=key)
            return {
                "etag": resp.get("ETag", "").strip('"'),
                "content_length": resp.get("ContentLength", 0),
                "last_modified": resp.get("LastModified"),
                "content_type": resp.get("ContentType", ""),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"Object not found: {key}")
            raise

    async def get_object(self, key: str) -> bytes:
        """Get object content."""
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {key}")
            raise

    async def put_object(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Put object. Returns ETag. Note: PutObject does NOT support if-match (§5.12)."""
        resp = self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return resp.get("ETag", "").strip('"')

    async def delete_object(self, key: str) -> None:
        """Delete object."""
        self._client.delete_object(Bucket=self._bucket, Key=key)

    async def list_objects(self, prefix: str, max_keys: int = 1000) -> list[dict[str, Any]]:
        """List objects under prefix. Handles pagination for OSS 1000-object limit (§4.6)."""
        objects = []
        continuation_token = None

        while True:
            kwargs = {
                "Bucket": self._bucket,
                "Prefix": prefix,
                "MaxKeys": min(max_keys - len(objects), 1000),
            }
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            resp = self._client.list_objects_v2(**kwargs)
            for obj in resp.get("Contents", []):
                objects.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                        "etag": obj.get("ETag", "").strip('"'),
                    }
                )

            if resp.get("IsTruncated") and len(objects) < max_keys:
                continuation_token = resp.get("NextContinuationToken")
            else:
                break

        return objects

    async def get_tags(self, key: str) -> dict[str, str]:
        """Get object tags."""
        try:
            resp = self._client.get_object_tagging(Bucket=self._bucket, Key=key)
            return {t["Key"]: t["Value"] for t in resp.get("TagSet", [])}
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Object not found: {key}")
            raise

    async def put_tags(self, key: str, tags: dict[str, str]) -> None:
        """Put object tags. PutObjectTagging does NOT require rewriting the object (§4.6)."""
        tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
        self._client.put_object_tagging(
            Bucket=self._bucket,
            Key=key,
            Tagging={"TagSet": tag_set},
        )

    async def get_entity_tag(self, entity_key: str) -> EntityTag:
        """Read Entity Tag from the source/original object."""
        tags = await self.get_tags(entity_key)
        return EntityTag(
            entity_type=tags.get("entity_type", "document"),
            mime_type=tags.get("mime_type", "application/octet-stream"),
            content_hash=tags.get("content_hash", ""),
            language=tags.get("language", "unknown"),
            size_bytes=tags.get("size_bytes", "0"),
            rag_status=tags.get("rag_status", "enabled"),
            entity_version=tags.get("entity_version", "1"),
        )

    async def put_entity_tag(self, entity_key: str, tag: EntityTag) -> None:
        """Write Entity Tag to the source/original object."""
        await self.put_tags(entity_key, tag.model_dump())

    async def get_rep_tag(self, rep_key: str) -> RepresentationTag | None:
        """Read Representation Tag from a representation file."""
        tags = await self.get_tags(rep_key)
        if "rep_type" not in tags:
            return None
        return RepresentationTag(
            rep_type=tags.get("rep_type", ""),
            pipeline_id=tags.get("pipeline_id", ""),
            transform=tags.get("transform", ""),
            modality=tags.get("modality", "text"),
            status=tags.get("status", "ready"),
            model_version=tags.get("model_version", ""),
            entity_version=tags.get("entity_version", "1"),
        )

    async def put_rep_tag(self, rep_key: str, tag: RepresentationTag) -> None:
        """Write Representation Tag to a representation file."""
        await self.put_tags(rep_key, tag.model_dump())

    async def compute_etag(self, key: str) -> str:
        """Get ETag via HeadObject (zero-download, §5.12.3 Phase 0)."""
        info = await self.head_object(key)
        return info["etag"]

    async def compute_content_hash(self, data: bytes) -> str:
        """Compute SHA-256 content hash."""
        return "sha256:" + hashlib.sha256(data).hexdigest()

    async def write_with_state_machine(
        self,
        key: str,
        data: bytes,
        tags: dict[str, str],
        content_type: str = "application/octet-stream",
    ) -> MetadataWriteState:
        """Write object + tags following the metadata write state machine (§5.12.2).

        State transitions:
        CLEAN → FILE_WRITTEN → MANIFEST_WRITTEN → TAG_MISSING → CLEAN

        v0.1: last-writer-wins + Reconciler fixes TAG_MISSING state.
        """
        # Step 1: Write file → FILE_WRITTEN
        await self.put_object(key, data, content_type)
        # Step 2: Write tags → CLEAN (if success) or TAG_MISSING (if failure)
        try:
            await self.put_tags(key, tags)
            return MetadataWriteState.CLEAN
        except Exception:
            return MetadataWriteState.TAG_MISSING

    async def object_exists(self, key: str) -> bool:
        """Check if object exists."""
        try:
            await self.head_object(key)
            return True
        except FileNotFoundError:
            return False

    async def copy_object(self, src_key: str, dst_key: str) -> str:
        """Copy object. Supports if-match for conditional writes (v0.2, §5.12)."""
        resp = self._client.copy_object(
            Bucket=self._bucket,
            Key=dst_key,
            CopySource={"Bucket": self._bucket, "Key": src_key},
        )
        return resp.get("CopyObjectResult", {}).get("ETag", "").strip('"')
