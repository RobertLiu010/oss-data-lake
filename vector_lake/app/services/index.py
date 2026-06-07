"""LanceDB index service with entity-level parquet persistence.

Architecture:
- Each entity's index data is stored as an independent parquet file:
  {root}/{ws}/{col}/{entity_id}/_index/{rep_name}.parquet
- LanceDB tables are derived views synced from these parquet files.
- Write path: chunks → entity parquet → LanceDB sync
- Read path (search): LanceDB (fast vector search)
- Rebuild path: scan entity parquets → recreate LanceDB table

This ensures:
1. Index data survives LanceDB corruption (parquet is source of truth)
2. Entity-level granularity for add/delete/sync
3. LanceDB can be rebuilt from parquet files at any time
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import lancedb
import pyarrow as pa
import pyarrow.parquet as pq

from app.config import Settings
from app.models.search import SearchResult

logger = logging.getLogger(__name__)

# Schema for entity index parquet files
INDEX_SCHEMA = pa.schema([
    pa.field("chunk_index", pa.int64()),
    pa.field("text", pa.string()),
    pa.field("embedding", pa.list_(pa.float32())),
    pa.field("metadata", pa.string()),
    pa.field("rep_name", pa.string()),
])


def _cast_embedding_fixed_dim(table: pa.Table, dimension: int) -> pa.Table:
    """Cast variable-length embedding column to fixed-dimension list.

    Only casts if all embedding vectors have exactly `dimension` elements.
    Otherwise, returns the table unchanged (variable-length).
    """
    if "embedding" not in table.column_names:
        return table
    embedding_col = table.column("embedding")
    # Check if all vectors have the expected dimension
    try:
        fixed_type = pa.list_(pa.float32(), dimension)
        casted = embedding_col.cast(fixed_type)
        idx = table.column_names.index("embedding")
        return table.set_column(idx, "embedding", casted)
    except (pa.ArrowInvalid, pa.ArrowNotImplementedError):
        # Vectors don't all have the same length as dimension — keep variable-length
        logger.debug(
            "Embedding vectors don't match dimension %d, keeping variable-length",
            dimension,
        )
        return table


def _cast_to_lance_schema(table: pa.Table, lance_schema: pa.Schema) -> pa.Table:
    """Cast table columns to match LanceDB table schema."""
    for field in lance_schema:
        col_name = field.name
        if col_name not in table.column_names:
            continue
        src_type = table.schema.field(col_name).type
        tgt_type = field.type
        if src_type != tgt_type:
            idx = table.column_names.index(col_name)
            casted = table.column(col_name).cast(tgt_type)
            table = table.set_column(idx, col_name, casted)
    return table


class IndexService:
    """Manage chunk vectors with entity-level parquet + LanceDB sync."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = lancedb.connect(settings.lance.data_dir)
        self.dimension = settings.embedding.dimension
        # Run schema migrations on startup
        from app.services.migration import run_migrations

        try:
            applied = run_migrations(self.db, settings)
            if applied:
                logger.info("Applied %d schema migration(s)", applied)
        except Exception:
            logger.exception("Schema migration failed — continuing with best-effort")

    @staticmethod
    def _table_name(workspace_id: str, collection_id: str) -> str:
        return f"{workspace_id}_{collection_id}_chunks"

    def _index_dir(self, workspace_id: str, collection_id: str, entity_id: str) -> Path:
        """Return the _index/staging directory for an entity (PRD §5.12)."""
        return (
            Path(self.settings.storage.local.root)
            / workspace_id / collection_id / entity_id / "_index" / "staging"
        )

    def _parquet_path(self, workspace_id: str, collection_id: str, entity_id: str, rep_name: str) -> Path:
        """Return the parquet file path for a specific rep's index."""
        return self._index_dir(workspace_id, collection_id, entity_id) / f"{rep_name}.parquet"

    # ------------------------------------------------------------------
    # Entity-level parquet I/O
    # ------------------------------------------------------------------

    def write_entity_parquet(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        chunks_with_vectors: list[dict[str, Any]],
        rep_name: str = "canonical_md",
    ) -> Path:
        """Write chunks+embeddings to entity-level parquet file.

        Each item in chunks_with_vectors should have keys:
            chunk_index, text, embedding, metadata

        The parquet file is stored at:
            {root}/{ws}/{col}/{entity_id}/_index/staging/{rep_name}.parquet

        Returns the path to the written parquet file.
        """
        index_dir = self._index_dir(workspace_id, collection_id, entity_id)
        index_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = index_dir / f"{rep_name}.parquet"

        # Build Arrow table
        chunk_indices: list[int] = []
        texts: list[str] = []
        embeddings: list[list[float]] = []
        metadata_json: list[str] = []
        rep_names: list[str] = []

        for item in chunks_with_vectors:
            chunk_indices.append(item["chunk_index"])
            texts.append(item["text"])
            embeddings.append(item["embedding"])
            metadata_json.append(json.dumps(item.get("metadata", {}), ensure_ascii=False))
            rep_names.append(rep_name)

        # Use variable-length list for embedding to avoid dimension mismatch
        schema = pa.schema([
            pa.field("chunk_index", pa.int64()),
            pa.field("text", pa.string()),
            pa.field("embedding", pa.list_(pa.float32())),
            pa.field("metadata", pa.string()),
            pa.field("rep_name", pa.string()),
        ])

        table = pa.table({
            "chunk_index": chunk_indices,
            "text": texts,
            "embedding": embeddings,
            "metadata": metadata_json,
            "rep_name": rep_names,
        }, schema=schema)

        # Atomic write: tmp + fsync + rename (same pattern as manifest)
        tmp_path = parquet_path.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp_path)
        tmp_path.replace(parquet_path)
        logger.info(
            "Wrote %d chunks to %s (entity %s, rep=%s)",
            len(chunks_with_vectors), parquet_path, entity_id, rep_name,
        )
        return parquet_path

    def read_entity_parquet(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_name: str = "canonical_md",
    ) -> pa.Table | None:
        """Read entity parquet file, returns Arrow Table or None."""
        parquet_path = self._parquet_path(workspace_id, collection_id, entity_id, rep_name)
        if not parquet_path.exists():
            return None
        return pq.read_table(parquet_path)

    def delete_entity_parquet(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_name: str | None = None,
    ) -> None:
        """Delete entity parquet file(s).

        If rep_name is None, delete all parquets for the entity.
        """
        if rep_name:
            parquet_path = self._parquet_path(workspace_id, collection_id, entity_id, rep_name)
            if parquet_path.exists():
                parquet_path.unlink()
                logger.info("Deleted parquet %s", parquet_path)
        else:
            index_dir = self._index_dir(workspace_id, collection_id, entity_id)
            if index_dir.exists():
                for f in index_dir.glob("*.parquet"):
                    f.unlink()
                    logger.info("Deleted parquet %s", f)

    def list_entity_parquets(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
    ) -> list[str]:
        """List rep_names that have parquet files for an entity."""
        index_dir = self._index_dir(workspace_id, collection_id, entity_id)
        if not index_dir.exists():
            return []
        return [f.stem for f in sorted(index_dir.glob("*.parquet"))]

    # ------------------------------------------------------------------
    # LanceDB sync
    # ------------------------------------------------------------------

    async def sync_to_lance(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        rep_name: str = "canonical_md",
    ) -> int:
        """Sync entity parquet data into LanceDB table.

        Reads the entity's parquet file, adds entity_id column,
        deletes old rows for (entity_id, rep_name), and inserts new data.

        Returns the number of rows synced.
        """
        parquet_table = self.read_entity_parquet(workspace_id, collection_id, entity_id, rep_name)
        if parquet_table is None or parquet_table.num_rows == 0:
            return 0

        table_name = self._table_name(workspace_id, collection_id)

        # Add entity_id column
        entity_id_col = pa.array([entity_id] * parquet_table.num_rows, type=pa.string())
        full_table = parquet_table.append_column("entity_id", entity_id_col)

        # Reorder columns to match LanceDB schema: entity_id first
        col_names = full_table.column_names
        ordered_names = ["entity_id"] + [c for c in col_names if c != "entity_id"]
        full_table = full_table.select(ordered_names)

        def _sync() -> int:
            existing_tables = self.db.list_tables().tables
            safe_id = entity_id.replace('"', '').replace("'", "")
            safe_rep = rep_name.replace('"', '').replace("'", "")

            if table_name in existing_tables:
                lance_table = self.db.open_table(table_name)
                # Delete old rows for this (entity_id, rep_name)
                lance_table.delete(f'entity_id = "{safe_id}" AND rep_name = "{safe_rep}"')
                # Cast embedding column to match LanceDB table schema
                lance_schema = lance_table.schema
                full_table_sync = _cast_to_lance_schema(full_table, lance_schema)
                lance_table.add(full_table_sync)
            else:
                # Cast embedding to fixed-dimension for new table
                full_table_sync = _cast_embedding_fixed_dim(full_table, self.dimension)
                lance_table = self.db.create_table(table_name, full_table_sync)
                # Create FTS index for hybrid search support
                try:
                    lance_table.create_fts_index("text", replace=True)
                    logger.info("Created FTS index on table %s", table_name)
                except Exception as e:
                    logger.debug("FTS index creation skipped for %s: %s", table_name, e)

            return full_table.num_rows

        count = await asyncio.get_event_loop().run_in_executor(None, _sync)
        logger.info(
            "Synced %d rows from parquet to LanceDB %s (entity=%s, rep=%s)",
            count, table_name, entity_id, rep_name,
        )
        return count

    async def rebuild_lance_table(
        self,
        workspace_id: str,
        collection_id: str,
    ) -> int:
        """Rebuild entire LanceDB table from all entity parquets.

        Scans all entities in the collection, reads their parquet files,
        and recreates the LanceDB table from scratch.

        Returns total rows synced.
        """
        table_name = self._table_name(workspace_id, collection_id)
        col_dir = Path(self.settings.storage.local.root) / workspace_id / collection_id
        if not col_dir.exists():
            return 0

        # Collect all parquet data
        all_tables: list[pa.Table] = []
        for entity_dir in sorted(col_dir.iterdir()):
            if not entity_dir.is_dir() or entity_dir.name.startswith("_"):
                continue
            entity_id = entity_dir.name
            index_dir = entity_dir / "_index" / "staging"
            if not index_dir.exists():
                continue
            for pq_file in sorted(index_dir.glob("*.parquet")):
                try:
                    t = pq.read_table(pq_file)
                    entity_id_col = pa.array([entity_id] * t.num_rows, type=pa.string())
                    t = t.append_column("entity_id", entity_id_col)
                    # Reorder
                    col_names = t.column_names
                    ordered_names = ["entity_id"] + [c for c in col_names if c != "entity_id"]
                    t = t.select(ordered_names)
                    all_tables.append(t)
                except Exception as e:
                    logger.warning("Failed to read parquet %s: %s", pq_file, e)

        if not all_tables:
            return 0

        combined = pa.concat_tables(all_tables)

        def _rebuild() -> int:
            # Cast embedding to fixed-dimension for LanceDB compatibility
            combined_sync = _cast_embedding_fixed_dim(combined, self.dimension)
            # Drop existing table and recreate
            if table_name in self.db.list_tables().tables:
                self.db.drop_table(table_name)
            lance_table = self.db.create_table(table_name, combined_sync)
            try:
                lance_table.create_fts_index("text", replace=True)
            except Exception as e:
                logger.debug("FTS index creation skipped: %s", e)
            return combined.num_rows

        count = await asyncio.get_event_loop().run_in_executor(None, _rebuild)
        logger.info(
            "Rebuilt LanceDB table %s with %d rows from %d parquet files",
            table_name, count, len(all_tables),
        )
        return count

    # ------------------------------------------------------------------
    # Upsert (write parquet ONLY — LanceDB sync is a separate operation)
    # ------------------------------------------------------------------

    async def upsert_chunks(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        chunks_with_vectors: list[dict[str, Any]],
        rep_name: str = "canonical_md",
    ) -> int:
        """Insert/update chunks into entity-level parquet file.

        This is the ONLY write API. It writes chunks to parquet only.
        LanceDB is NOT updated here — call sync_to_lance() separately.

        Architecture: parquet is the single source of truth.
        LanceDB is a derived view that must be synced from parquet.

        Each item in chunks_with_vectors should have keys:
            chunk_index, text, embedding, metadata
        """
        self.write_entity_parquet(
            workspace_id, collection_id, entity_id,
            chunks_with_vectors, rep_name,
        )
        return len(chunks_with_vectors)

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def table_exists(self, workspace_id: str, collection_id: str) -> bool:
        """Check whether the LanceDB table exists for a workspace/collection."""
        table_name = self._table_name(workspace_id, collection_id)
        return table_name in self.db.list_tables().tables

    def drop_table(self, workspace_id: str, collection_id: str) -> None:
        """Drop the entire LanceDB table for a workspace/collection."""
        table_name = self._table_name(workspace_id, collection_id)
        if table_name not in self.db.list_tables().tables:
            return
        self.db.drop_table(table_name)
        logger.info("Dropped LanceDB table %s", table_name)

    def count_entity_chunks(self, workspace_id: str, collection_id: str, entity_id: str) -> int:
        """Count indexed chunks for a specific entity. Returns 0 if table doesn't exist."""
        # Fast path: count from parquet files
        index_dir = self._index_dir(workspace_id, collection_id, entity_id)
        if index_dir.exists():
            total = 0
            for pq_file in index_dir.glob("*.parquet"):
                try:
                    total += pq.read_metadata(pq_file).num_rows
                except Exception:
                    pass
            return total

        # Fallback: query LanceDB
        table_name = self._table_name(workspace_id, collection_id)
        if table_name not in self.db.list_tables().tables:
            return 0

        table = self.db.open_table(table_name)
        try:
            return table.count_rows(filter=f'entity_id = "{entity_id}"')
        except Exception:
            return 0

    def delete_entity_chunks(self, workspace_id: str, collection_id: str, entity_id: str) -> None:
        """Delete all chunks for an entity (parquet + LanceDB)."""
        # Delete parquet files
        self.delete_entity_parquet(workspace_id, collection_id, entity_id)

        # Delete from LanceDB
        table_name = self._table_name(workspace_id, collection_id)
        if table_name not in self.db.list_tables().tables:
            return

        table = self.db.open_table(table_name)
        safe_id = entity_id.replace('"', '').replace("'", "")
        table.delete(f'entity_id = "{safe_id}"')

    def get_indexed_entity_ids(self, workspace_id: str, collection_id: str) -> set[str]:
        """Get the set of entity_ids that have index parquet files."""
        col_dir = Path(self.settings.storage.local.root) / workspace_id / collection_id
        if not col_dir.exists():
            return set()

        result = set()
        for entity_dir in sorted(col_dir.iterdir()):
            if not entity_dir.is_dir() or entity_dir.name.startswith("_"):
                continue
            index_dir = entity_dir / "_index" / "staging"
            if index_dir.exists() and any(index_dir.glob("*.parquet")):
                result.add(entity_dir.name)
        return result

    # ------------------------------------------------------------------
    # Search (reads from LanceDB for performance)
    # ------------------------------------------------------------------

    async def search(
        self,
        workspace_id: str,
        collection_id: str,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search by vector, return top_k results."""
        table_name = self._table_name(workspace_id, collection_id)

        existing_tables = self.db.list_tables().tables
        if table_name not in existing_tables:
            return []

        def _search() -> list[SearchResult]:
            table = self.db.open_table(table_name)
            results = (
                table.search(query_vector)
                .limit(top_k)
                .to_list()
            )
            out: list[SearchResult] = []
            for row in results:
                meta = {}
                raw_meta = row.get("metadata")
                if isinstance(raw_meta, str):
                    try:
                        meta = json.loads(raw_meta)
                    except json.JSONDecodeError:
                        meta = {}
                elif isinstance(raw_meta, dict):
                    meta = raw_meta

                out.append(SearchResult(
                    entity_id=row.get("entity_id", ""),
                    chunk_index=int(row.get("chunk_index", 0)),
                    text=row.get("text", ""),
                    score=float(row.get("_distance", 0.0)),
                    metadata=meta,
                    search_type="semantic",
                    rep_name=row.get("rep_name", "canonical_md"),
                ))
            return out

        return await asyncio.get_event_loop().run_in_executor(None, _search)

    # ------------------------------------------------------------------
    # Lexical search
    # ------------------------------------------------------------------

    async def search_lexical(
        self,
        workspace_id: str,
        collection_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search by text matching on the `text` column."""
        table_name = self._table_name(workspace_id, collection_id)

        existing_tables = self.db.list_tables().tables
        if table_name not in existing_tables:
            return []

        def _search() -> list[SearchResult]:
            table = self.db.open_table(table_name)
            try:
                results = table.search(query, query_type="fts").limit(top_k).to_list()
            except Exception:
                try:
                    table.create_fts_index("text", replace=True)
                    results = table.search(query, query_type="fts").limit(top_k).to_list()
                except Exception:
                    logger.warning("FTS unavailable for %s, falling back to filtered search", table_name)
                    query_lower = query.lower()
                    try:
                        rows = table.search().limit(10_000).to_list()
                        results = [
                            r for r in rows
                            if query_lower in (r.get("text", "") or "").lower()
                        ][:top_k]
                    except Exception:
                        results = []

            out: list[SearchResult] = []
            for rank, row in enumerate(results):
                meta = {}
                raw_meta = row.get("metadata")
                if isinstance(raw_meta, str):
                    try:
                        meta = json.loads(raw_meta)
                    except json.JSONDecodeError:
                        meta = {}
                elif isinstance(raw_meta, dict):
                    meta = raw_meta

                out.append(SearchResult(
                    entity_id=row.get("entity_id", ""),
                    chunk_index=int(row.get("chunk_index", 0)),
                    text=row.get("text", ""),
                    score=float(row.get("_relevance_score", 1.0 / (rank + 1))),
                    metadata=meta,
                    search_type="lexical",
                    rep_name=row.get("rep_name", "canonical_md"),
                ))
            return out

        return await asyncio.get_event_loop().run_in_executor(None, _search)

    # ------------------------------------------------------------------
    # Hybrid search (RRF)
    # ------------------------------------------------------------------

    async def search_hybrid(
        self,
        workspace_id: str,
        collection_id: str,
        query: str,
        query_vector: list[float],
        top_k: int = 5,
        rrf_k: int = 60,
        semantic_weight: float = 0.7,
        lexical_weight: float = 0.3,
    ) -> list[SearchResult]:
        """Hybrid search using Reciprocal Rank Fusion (RRF)."""
        fetch_k = top_k * 3

        semantic_results, lexical_results = await asyncio.gather(
            self.search(workspace_id, collection_id, query_vector, top_k=fetch_k),
            self.search_lexical(workspace_id, collection_id, query, top_k=fetch_k),
        )

        merged: dict[tuple, float] = {}
        data_map: dict[tuple, SearchResult] = {}

        for rank, result in enumerate(semantic_results):
            key = (result.entity_id, result.chunk_index)
            rrf_score = semantic_weight / (rrf_k + rank + 1)
            merged[key] = merged.get(key, 0.0) + rrf_score
            data_map[key] = result

        for rank, result in enumerate(lexical_results):
            key = (result.entity_id, result.chunk_index)
            rrf_score = lexical_weight / (rrf_k + rank + 1)
            merged[key] = merged.get(key, 0.0) + rrf_score
            if key not in data_map:
                data_map[key] = result

        sorted_keys = sorted(merged.keys(), key=lambda k: merged[k], reverse=True)[:top_k]

        out: list[SearchResult] = []
        for key in sorted_keys:
            result = data_map[key]
            out.append(SearchResult(
                entity_id=result.entity_id,
                chunk_index=result.chunk_index,
                text=result.text,
                score=merged[key],
                metadata=result.metadata,
                search_type="hybrid",
                rep_name=result.rep_name,
            ))
        return out
