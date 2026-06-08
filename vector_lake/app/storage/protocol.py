"""Storage abstraction protocol — defines the contract for all storage backends.

Implementations:
- LocalStorage: local filesystem + xattr
- S3Storage: S3/MinIO-compatible object storage
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StorageProtocol(Protocol):
    """Protocol defining the storage backend contract.

    All storage implementations must satisfy this interface.
    The `root` attribute is a Path for local backends, or a pseudo-Path
    (e.g. s3://bucket/prefix) for object storage backends.
    """

    root: Path

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
    ) -> str: ...

    def read_file(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
    ) -> bytes | None: ...

    def file_exists(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
    ) -> bool: ...

    def list_entities(self, workspace_id: str, collection_id: str) -> list[str]: ...

    # ------------------------------------------------------------------
    # Entity Tags (OSS Tag simulation — best-effort cache)
    # ------------------------------------------------------------------

    def set_entity_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        tags: dict[str, str],
    ) -> None: ...

    def get_entity_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> dict[str, str]: ...

    # ------------------------------------------------------------------
    # Representation Tags
    # ------------------------------------------------------------------

    def set_rep_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
        tags: dict[str, str],
    ) -> None: ...

    def get_rep_tags(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
    ) -> dict[str, str]: ...

    # ------------------------------------------------------------------
    # Entity Manifest (single source of truth)
    # ------------------------------------------------------------------

    def save_entity_manifest(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        manifest: dict,
    ) -> None: ...

    def read_entity_manifest(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> dict | None: ...

    def sync_tags_from_manifest(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> None: ...

    def assemble_entity(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> dict | None: ...

    # ------------------------------------------------------------------
    # Version log (append-only history, PRD §5.12)
    # ------------------------------------------------------------------

    def append_version_log(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        version: int,
        content_hash: str,
        trigger: str = "update",
    ) -> None: ...

    def read_version_log(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> list[dict]: ...

    # ------------------------------------------------------------------
    # Workspace / Collection management (pluggable storage support)
    # ------------------------------------------------------------------

    def list_workspaces(self) -> list[str]:
        """List all workspace IDs."""
        ...

    def list_collections(self, workspace_id: str) -> list[str]:
        """List all collection IDs under a workspace."""
        ...

    def create_workspace(self, workspace_id: str) -> None:
        """Create a workspace (directory or sentinel object)."""
        ...

    def create_collection(self, workspace_id: str, collection_id: str) -> None:
        """Create a collection (directory or sentinel object)."""
        ...

    def delete_workspace(self, workspace_id: str) -> None:
        """Delete a workspace and all its contents."""
        ...

    def delete_collection(self, workspace_id: str, collection_id: str) -> None:
        """Delete a collection and all its contents."""
        ...

    def entity_dir_exists(self, workspace_id: str, collection_id: str, entity_id: str) -> bool:
        """Check if an entity directory/prefix exists."""
        ...


# Type alias for storage instances
StorageBackend = StorageProtocol
