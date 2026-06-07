"""LanceDB index service."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import lancedb
import pyarrow as pa

from app.config import Settings
from app.models.search import SearchResult

logger = logging.getLogger(__name__)


class IndexService:
    """Manage chunk vectors in LanceDB."""

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

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    async def upsert_chunks(
        self,
        workspace_id: str,
        collection_id: str,
        entity_id: str,
        chunks_with_vectors: list[dict[str, Any]],
    ) -> int:
        """Insert/update chunks into LanceDB table.

        Each item in *chunks_with_vectors* should have keys:
            chunk_index, text, embedding, metadata
        """
        table_name = self._table_name(workspace_id, collection_id)

        # Build Arrow table data
        entity_ids: list[str] = []
        chunk_indices: list[int] = []
        texts: list[str] = []
        embeddings: list[list[float]] = []
        metadata_json: list[str] = []

        for item in chunks_with_vectors:
            entity_ids.append(entity_id)
            chunk_indices.append(item["chunk_index"])
            texts.append(item["text"])
            embeddings.append(item["embedding"])
            metadata_json.append(json.dumps(item.get("metadata", {}), ensure_ascii=False))

        schema = pa.schema([
            pa.field("entity_id", pa.string()),
            pa.field("chunk_index", pa.int64()),
            pa.field("text", pa.string()),
            pa.field("embedding", pa.list_(pa.float32(), self.dimension)),
            pa.field("metadata", pa.string()),
        ])

        new_data = pa.table({
            "entity_id": entity_ids,
            "chunk_index": chunk_indices,
            "text": texts,
            "embedding": embeddings,
            "metadata": metadata_json,
        }, schema=schema)

        def _upsert() -> int:
            existing_tables = self.db.list_tables().tables
            if table_name in existing_tables:
                table = self.db.open_table(table_name)
                # Delete old chunks for this entity before adding new ones
                safe_id = entity_id.replace('"', '').replace("'", "")
                table.delete(f'entity_id = "{safe_id}"')
                table.add(new_data)
            else:
                table = self.db.create_table(table_name, new_data)
                # Best practice: create FTS index immediately for hybrid search support
                try:
                    table.create_fts_index("text", replace=True)
                    logger.info("Created FTS index on table %s", table_name)
                except Exception as e:
                    logger.debug("FTS index creation skipped for %s: %s", table_name, e)
            return len(chunks_with_vectors)

        count = await asyncio.get_event_loop().run_in_executor(None, _upsert)
        logger.info(
            "Upserted %d chunks for entity %s in %s",
            count, entity_id, table_name,
        )
        return count

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
        table_name = self._table_name(workspace_id, collection_id)
        if table_name not in self.db.list_tables().tables:
            return 0

        table = self.db.open_table(table_name)
        try:
            return table.count_rows(filter=f'entity_id = "{entity_id}"')
        except (AttributeError, TypeError):
            pass
        except Exception:
            pass

        # Fallback: scan without count_rows
        try:
            rows = table.search().where(f'entity_id = "{entity_id}"').limit(10_000).to_list()
            return len(rows)
        except Exception:
            return 0

    def delete_entity_chunks(self, workspace_id: str, collection_id: str, entity_id: str) -> None:
        """Delete all chunks for an entity."""
        table_name = self._table_name(workspace_id, collection_id)
        if table_name not in self.db.list_tables().tables:
            return

        table = self.db.open_table(table_name)
        safe_id = entity_id.replace('"', '').replace("'", "")
        table.delete(f'entity_id = "{safe_id}"')

    def get_indexed_entity_ids(self, workspace_id: str, collection_id: str) -> set[str]:
        """Get the set of entity_ids that have chunks in the index."""
        table_name = self._table_name(workspace_id, collection_id)
        if table_name not in self.db.list_tables().tables:
            return set()

        table = self.db.open_table(table_name)
        try:
            # Use to_pandas if pandas is available (fast path)
            import pandas  # noqa: F401
            df = table.to_pandas(limit=50_000)
            return set(df["entity_id"].unique())
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: scan without pandas
        try:
            rows = table.search().limit(50_000).to_list()
            return {r.get("entity_id", "") for r in rows if r.get("entity_id")}
        except Exception:
            return set()

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
            # Use LanceDB's native full-text search (best practice: avoid materializing)
            try:
                results = table.search(query, query_type="fts").limit(top_k).to_list()
            except Exception:
                # If FTS index doesn't exist, create it and retry
                try:
                    table.create_fts_index("text", replace=True)
                    results = table.search(query, query_type="fts").limit(top_k).to_list()
                except Exception:
                    # Last resort: scan rows and filter in Python (no pandas needed)
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
        """Hybrid search using Reciprocal Rank Fusion (RRF).

        1. Run both semantic and lexical search with expanded top_k.
        2. Compute RRF score for each result: 1 / (k + rank).
        3. Merge by (entity_id, chunk_index), summing weighted RRF scores.
        4. Return merged results sorted by combined score.
        """
        # Fetch more candidates to ensure good fusion coverage
        fetch_k = top_k * 3

        semantic_results, lexical_results = await asyncio.gather(
            self.search(workspace_id, collection_id, query_vector, top_k=fetch_k),
            self.search_lexical(workspace_id, collection_id, query, top_k=fetch_k),
        )

        # Compute RRF scores and merge
        merged: dict[tuple, float] = {}  # (entity_id, chunk_index) -> combined score
        data_map: dict[tuple, SearchResult] = {}  # keep the SearchResult for key

        for rank, result in enumerate(semantic_results):
            key = (result.entity_id, result.chunk_index)
            rrf_score = semantic_weight / (rrf_k + rank + 1)
            merged[key] = merged.get(key, 0.0) + rrf_score
            data_map[key] = result

        for rank, result in enumerate(lexical_results):
            key = (result.entity_id, result.chunk_index)
            rrf_score = lexical_weight / (rrf_k + rank + 1)
            merged[key] = merged.get(key, 0.0) + rrf_score
            # Prefer keeping the semantic result's data; only store if not present
            if key not in data_map:
                data_map[key] = result

        # Sort by combined RRF score descending
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
            ))
        return out
