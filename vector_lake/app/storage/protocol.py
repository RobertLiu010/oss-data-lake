"""Storage abstraction protocol — defines the contract for all storage backends.

Implementations:
- LocalStorage: local filesystem + xattr
- Planned: S3Storage, OSSStorage (v0.2)
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class StorageProtocol(Protocol):
    """Protocol defining the storage backend contract.

    All storage implementations must satisfy this interface.
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


# Type alias for storage instances
StorageBackend = StorageProtocol
