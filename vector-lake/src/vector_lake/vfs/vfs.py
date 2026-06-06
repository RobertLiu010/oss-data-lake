"""Virtual File System (§8.2): ls, stat, read, grep, glob over OSS."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from vector_lake.models.entity import Entity
from vector_lake.models.enums import EntityStatus
from vector_lake.models.representation import Representation
from vector_lake.vfs.path_resolver import resolve_rep_path
from vector_lake.vfs.storage import ObjectStorage


@dataclass
class VFSStat:
    """VFS stat result."""

    path: str
    is_dir: bool
    size: int = 0
    etag: str = ""
    last_modified: str = ""
    tags: dict[str, str] | None = None
    entity: Entity | None = None
    representation: Representation | None = None


class VFS:
    """Virtual File System over OSS (§8.2).

    Provides: ls, stat, read, grep, glob
    All metadata derived from OSS Tag + path structure (quasi-zero-persistence).
    """

    def __init__(self, storage: ObjectStorage):
        self._storage = storage

    async def ls(self, prefix: str, recursive: bool = False) -> list[str]:
        """List directory contents under prefix."""
        objects = await self._storage.list_objects(prefix)
        keys = [obj["key"] for obj in objects]
        if not recursive:
            # Return unique directory prefixes at the next level
            prefix_len = len(prefix.rstrip("/")) + 1
            seen: set[str] = set()
            result = []
            for key in keys:
                remainder = key[prefix_len:]
                first_part = remainder.split("/")[0]
                dir_path = f"{prefix.rstrip('/')}/{first_part}"
                if dir_path not in seen:
                    seen.add(dir_path)
                    result.append(dir_path)
            return result
        return keys

    async def stat(self, path: str) -> VFSStat:
        """Get metadata for a path (§8.2 stat)."""
        # Try as file first
        try:
            info = await self._storage.head_object(path)
            tags = await self._storage.get_tags(path)
            return VFSStat(
                path=path,
                is_dir=False,
                size=info["content_length"],
                etag=info["etag"],
                last_modified=str(info.get("last_modified", "")),
                tags=tags,
            )
        except FileNotFoundError:
            pass

        # Try as directory prefix
        objects = await self._storage.list_objects(path.rstrip("/") + "/", max_keys=1)
        if objects:
            return VFSStat(path=path, is_dir=True)
        raise FileNotFoundError(f"Path not found: {path}")

    async def read(self, key: str) -> bytes:
        """Read file content (§8.2 read)."""
        return await self._storage.get_object(key)

    async def grep(
        self,
        pattern: str,
        prefix: str,
        max_results: int = 20,
    ) -> list[dict[str, Any]]:
        """Grep (text search) across files under prefix (§8.2 grep).

        Iterative scanning — reads text files and matches pattern.
        """
        results: list[dict[str, Any]] = []
        compiled = re.compile(pattern, re.IGNORECASE)
        objects = await self._storage.list_objects(prefix)

        for obj in objects:
            if len(results) >= max_results:
                break
            key = obj["key"]
            # Only scan text-like files
            if not any(key.endswith(ext) for ext in (".md", ".txt", ".json", ".csv")):
                continue
            try:
                content = await self._storage.get_object(key)
                text = content.decode("utf-8", errors="replace")
                for line_no, line in enumerate(text.splitlines(), 1):
                    if compiled.search(line):
                        results.append(
                            {
                                "file": key,
                                "line": line_no,
                                "content": line.strip()[:200],
                            }
                        )
                        if len(results) >= max_results:
                            break
            except Exception:
                continue

        return results

    async def glob(self, pattern: str, prefix: str = "") -> list[str]:
        """Glob pattern matching over OSS keys (§8.2 glob)."""
        objects = await self._storage.list_objects(prefix or "vector-lake/")
        keys = [obj["key"] for obj in objects]
        # Simple glob: convert * to regex
        regex = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
        compiled = re.compile(f"^{regex}$")
        return [k for k in keys if compiled.match(k)]

    async def get_entity(self, workspace_id: str, collection_id: str, entity_id: str) -> Entity:
        """Get entity by reading Entity Tag from source/original."""
        source_key = f"vector-lake/{workspace_id}/{collection_id}/{entity_id}/source/original"
        tag = await self._storage.get_entity_tag(source_key)
        return Entity(
            entity_id=entity_id,
            workspace_id=workspace_id,
            collection_id=collection_id,
            entity_type=tag.entity_type,
            mime_type=tag.mime_type,
            content_hash=tag.content_hash,
            language=tag.language,
            size_bytes=int(tag.size_bytes),
            rag_status=tag.rag_status,
            version=int(tag.entity_version),
            status=EntityStatus(tag.rag_status)
            if tag.rag_status in ("enabled", "hidden", "deleted")
            else EntityStatus.ENABLED,
        )

    async def list_representations(
        self, workspace_id: str, collection_id: str, entity_id: str
    ) -> list[Representation]:
        """List all representations for an entity by scanning OSS tags."""
        entity_prefix = f"vector-lake/{workspace_id}/{collection_id}/{entity_id}/"
        objects = await self._storage.list_objects(entity_prefix)
        reps = []
        for obj in objects:
            key = obj["key"]
            # Skip _index/ directory
            if "/_index/" in key:
                continue
            # Skip source/original (that's the entity, not a rep)
            if key.endswith("/source/original"):
                continue
            try:
                tag = await self._storage.get_rep_tag(key)
                if tag:
                    reps.append(Representation.from_tag(entity_id, tag, oss_uri=key))
            except Exception:
                continue
        return reps

    async def get_representation_content(
        self, workspace_id: str, collection_id: str, entity_id: str, rep_type: str
    ) -> bytes:
        """Read representation file content."""
        path = resolve_rep_path(workspace_id, collection_id, entity_id, rep_type)
        return await self._storage.get_object(path)
