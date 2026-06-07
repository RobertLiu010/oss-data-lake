"""VFS service — Virtual File System over local storage.

Maps the physical layout {root}/{ws}/{col}/{entity_id}/{rep_type}
to virtual paths: /{entity_name}/{rep_type}

Provides: ls, stat, read, glob, grep.
"""

from __future__ import annotations

import fnmatch
import logging
import re
import time
from pathlib import Path

from app.config import Settings
from app.models.vfs import (
    VfsEntry,
    VfsGrepMatch,
    VfsStatResponse,
)
from app.storage.local import LocalStorage

logger = logging.getLogger(__name__)

HIDDEN_FILES = {".entity_manifest.json"}

# rep_type → virtual file name mapping
REP_TYPE_MAP = {
    "source_original": "original",
    "canonical_md": "canonical.md",
}

# Reverse: virtual name → rep_type
VIRTUAL_NAME_TO_REP = {v: k for k, v in REP_TYPE_MAP.items() if v is not None}

# Text rep_types that grep can scan
TEXT_REP_TYPES = {"source_original", "canonical_md"}


class VfsService:
    """Virtual File System service over LocalStorage."""

    def __init__(self, storage: LocalStorage, settings: Settings):
        self.storage = storage
        self.settings = settings
        self.root = Path(settings.storage.local.root)
        self._cache: dict[str, dict] = {}
        self._cache_ttl: float = settings.vfs.cache_ttl
        self._cache_timestamps: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _col_dir(self, ws: str, col: str) -> Path:
        return self.root / ws / col

    def _load_entity_meta(self, entity_dir: Path, ws: str, col: str) -> dict | None:
        """Load entity meta from OSS Tag + manifest (PRD §4.1)."""
        entity_id = entity_dir.name
        data = self.storage.assemble_entity(ws, col, entity_id)
        if data:
            return data
        return None

    def _entity_name(self, meta: dict | None, entity_id: str) -> str:
        if meta and meta.get("name"):
            return meta["name"]
        return entity_id

    def _rep_to_virtual_name(self, rep_type: str) -> str | None:
        return REP_TYPE_MAP.get(rep_type, rep_type)

    def _virtual_name_to_rep(self, vname: str) -> str | None:
        if vname in VIRTUAL_NAME_TO_REP:
            return VIRTUAL_NAME_TO_REP[vname]
        # fallback: treat virtual name as rep_type directly
        return vname

    def _is_text_rep(self, rep_type: str) -> bool:
        return rep_type in TEXT_REP_TYPES

    def _build_virtual_tree(self, ws: str, col: str) -> dict:
        """Build a flat virtual path → (entity_id, rep_type, file_path) mapping.

        Returns dict like:
          {"/pricing.pdf": (entity_id, None, entity_dir),
           "/pricing.pdf/original": (entity_id, "source_original", file_path),
           "/pricing.pdf/canonical.md": (entity_id, "canonical_md", file_path),
           ...}
        """
        col_dir = self._col_dir(ws, col)
        tree: dict = {}

        if not col_dir.exists():
            return tree

        for entity_dir in sorted(col_dir.iterdir()):
            if not entity_dir.is_dir():
                continue
            entity_id = entity_dir.name
            meta = self._load_entity_meta(entity_dir, ws, col)
            entity_name = self._entity_name(meta, entity_id)

            # Dir entry for the entity
            tree[f"/{entity_name}"] = {
                "entity_id": entity_id,
                "rep_type": None,
                "path": entity_dir,
                "meta": meta,
                "type": "dir",
            }

            # File entries for each rep
            for rep_file in sorted(entity_dir.iterdir()):
                if not rep_file.is_file():
                    continue
                rep_type = rep_file.name
                if rep_type in HIDDEN_FILES:
                    continue  # hidden
                vname = self._rep_to_virtual_name(rep_type)
                if vname is None:
                    continue
                tree[f"/{entity_name}/{vname}"] = {
                    "entity_id": entity_id,
                    "rep_type": rep_type,
                    "path": rep_file,
                    "meta": meta,
                    "type": "file",
                    "size": rep_file.stat().st_size,
                }

        return tree

    def _get_tree_cached(self, ws: str, col: str) -> dict:
        """Return the virtual tree for ws/col, using a TTL-based cache."""
        key = f"{ws}/{col}"
        now = time.monotonic()
        ts = self._cache_timestamps.get(key)
        if ts is not None and (now - ts) < self._cache_ttl and key in self._cache:
            return self._cache[key]
        tree = self._build_virtual_tree(ws, col)
        self._cache[key] = tree
        self._cache_timestamps[key] = now
        return tree

    def invalidate_cache(self, ws: str, col: str) -> None:
        """Clear cache for a specific ws/col."""
        key = f"{ws}/{col}"
        self._cache.pop(key, None)
        self._cache_timestamps.pop(key, None)

    def invalidate_all_cache(self) -> None:
        """Clear all cached trees."""
        self._cache.clear()
        self._cache_timestamps.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ls(self, ws: str, col: str, path: str = "/") -> list[VfsEntry]:
        """List entries under a virtual path."""
        tree = self._get_tree_cached(ws, col)

        # Normalize path
        path = path.rstrip("/") or "/"

        if path == "/":
            # List top-level entities (dirs only)
            prefix = "/"
            entries = []
            for vpath, info in tree.items():
                if info["type"] == "dir" and vpath.count("/") == 1:
                    meta = info.get("meta") or {}
                    entries.append(VfsEntry(
                        name=vpath.lstrip("/"),
                        path=vpath,
                        type="dir",
                        entity_id=info["entity_id"],
                        entity_type=meta.get("entity_type"),
                        status=meta.get("status"),
                    ))
            return entries

        # List children under a specific entity dir
        prefix = path + "/"
        entries = []
        for vpath, info in tree.items():
            if vpath.startswith(prefix) and vpath.count("/") == path.count("/") + 1:
                meta = info.get("meta") or {}
                name = vpath[len(prefix):]
                size = info.get("size", 0) if info["type"] == "file" else 0
                entries.append(VfsEntry(
                    name=name,
                    path=vpath,
                    type=info["type"],
                    size=size,
                    entity_id=info["entity_id"],
                    rep_type=info.get("rep_type"),
                    entity_type=meta.get("entity_type"),
                    status=meta.get("status"),
                ))
        return entries

    def stat(self, ws: str, col: str, path: str) -> VfsStatResponse | None:
        """Get metadata for a virtual path."""
        tree = self._get_tree_cached(ws, col)
        path = path.rstrip("/") or "/"

        info = tree.get(path)
        if info is None:
            return None

        meta = info.get("meta") or {}
        size = info.get("size", 0) if info["type"] == "file" else 0

        return VfsStatResponse(
            path=path,
            type=info["type"],
            size=size,
            entity_id=info["entity_id"],
            rep_type=info.get("rep_type"),
            entity_type=meta.get("entity_type"),
            name=meta.get("name"),
            status=meta.get("status"),
            content_hash=meta.get("content_hash"),
            version=meta.get("version"),
            labels=meta.get("labels", []),
        )

    def read(self, ws: str, col: str, path: str) -> tuple[str, str, str] | None:
        """Read file content at virtual path.

        Returns (content, entity_id, rep_type) or None.
        """
        tree = self._get_tree_cached(ws, col)
        path = path.rstrip("/")

        info = tree.get(path)
        if info is None or info["type"] != "file":
            return None

        file_path: Path = info["path"]
        if not file_path.exists():
            return None

        try:
            content = file_path.read_text("utf-8", errors="replace")
        except Exception:
            content = f"<binary file, {file_path.stat().st_size} bytes>"

        return content, info["entity_id"], info.get("rep_type", "")

    def glob(self, ws: str, col: str, pattern: str) -> list[VfsEntry]:
        """Glob match over virtual paths.

        Supports patterns like:
          **/*.md          — all .md files
          **/canonical.md  — all canonical.md files
          /pricing*/**     — everything under pricing* dirs
        """
        tree = self._get_tree_cached(ws, col)
        results = []

        for vpath, info in tree.items():
            if fnmatch.fnmatch(vpath, pattern):
                meta = info.get("meta") or {}
                size = info.get("size", 0) if info["type"] == "file" else 0
                name = vpath.rsplit("/", 1)[-1] if "/" in vpath else vpath.lstrip("/")
                results.append(VfsEntry(
                    name=name,
                    path=vpath,
                    type=info["type"],
                    size=size,
                    entity_id=info["entity_id"],
                    rep_type=info.get("rep_type"),
                    entity_type=meta.get("entity_type"),
                    status=meta.get("status"),
                ))

        return results

    def grep(
        self,
        ws: str,
        col: str,
        pattern: str,
        path_prefix: str = "/",
        max_results: int = 50,
        context_lines: int = 2,
    ) -> list[VfsGrepMatch]:
        """Grep over text files in VFS.

        1. Glob to find candidate files under path_prefix
        2. Filter to text rep_types only
        3. Read + regex match each file
        4. Return matches with context
        """
        tree = self._get_tree_cached(ws, col)
        path_prefix = path_prefix.rstrip("/") or "/"

        # Collect candidate text files
        candidates = []
        for vpath, info in tree.items():
            if info["type"] != "file":
                continue
            if not self._is_text_rep(info.get("rep_type", "")):
                continue
            if path_prefix != "/" and not vpath.startswith(path_prefix):
                continue
            candidates.append((vpath, info))

        # Compile regex
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            logger.warning("Invalid grep pattern %r: %s", pattern, e)
            return []

        matches: list[VfsGrepMatch] = []

        for vpath, info in candidates:
            if len(matches) >= max_results:
                break

            file_path: Path = info["path"]
            if not file_path.exists():
                continue

            try:
                lines = file_path.read_text("utf-8", errors="replace").splitlines()
            except Exception:
                continue

            meta = info.get("meta") or {}

            for i, line in enumerate(lines):
                if len(matches) >= max_results:
                    break
                if regex.search(line):
                    before = lines[max(0, i - context_lines):i]
                    after = lines[i + 1:i + 1 + context_lines]
                    matches.append(VfsGrepMatch(
                        file_path=vpath,
                        line_number=i + 1,
                        line_text=line,
                        context_before=before,
                        context_after=after,
                        entity_id=info["entity_id"],
                        rep_type=info.get("rep_type"),
                        entity_type=meta.get("entity_type"),
                        name=meta.get("name"),
                    ))

        return matches
