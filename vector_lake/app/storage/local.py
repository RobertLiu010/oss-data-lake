from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.config import Settings


class LocalStorage:
    """Local filesystem storage for entity representations."""

    def __init__(self, settings: Settings):
        self.root = settings.storage.local.root
        Path(self.root).mkdir(parents=True, exist_ok=True)

    def _entity_dir(self, workspace_id: str, collection_id: str, entity_id: str) -> Path:
        return Path(self.root) / workspace_id / collection_id / entity_id

    def save_file(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_type: str,
        content: bytes,
    ) -> str:
        """Save content bytes to {root}/{ws}/{col}/{entity_id}/{rep_type}.

        Returns the absolute path of the saved file.
        """
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
        """List entity_ids by scanning the directory for {root}/{ws}/{col}/."""
        col_dir = Path(self.root) / workspace_id / collection_id
        if not col_dir.exists():
            return []
        return [
            d.name
            for d in sorted(col_dir.iterdir())
            if d.is_dir()
        ]
