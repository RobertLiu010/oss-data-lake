"""LanceDB index service."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import lancedb
import pyarrow as pa

from app.config import Settings
from app.models.search import SearchResult

logger = logging.getLogger(__name__)


class IndexService:
    """Manage chunk vectors in LanceDB."""

    def __init__(self, settings: Settings):
        self.db = lancedb.connect(settings.lance.data_dir)
        self.dimension = settings.embedding.dimension

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
        chunks_with_vectors: List[Dict[str, Any]],
    ) -> int:
        """Insert/update chunks into LanceDB table.

        Each item in *chunks_with_vectors* should have keys:
            chunk_index, text, embedding, metadata
        """
        table_name = self._table_name(workspace_id, collection_id)

        # Build Arrow table data
        entity_ids: List[str] = []
        chunk_indices: List[int] = []
        texts: List[str] = []
        embeddings: List[List[float]] = []
        metadata_json: List[str] = []

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
            existing_tables = self.db.table_names()
            if table_name in existing_tables:
                table = self.db.open_table(table_name)
                # Delete old chunks for this entity before adding new ones
                table.delete(f'entity_id = "{entity_id}"')
                table.add(new_data)
            else:
                self.db.create_table(table_name, new_data)
            return len(chunks_with_vectors)

        count = await asyncio.get_event_loop().run_in_executor(None, _upsert)
        logger.info(
            "Upserted %d chunks for entity %s in %s",
            count, entity_id, table_name,
        )
        return count

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        workspace_id: str,
        collection_id: str,
        query_vector: List[float],
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Search by vector, return top_k results."""
        table_name = self._table_name(workspace_id, collection_id)

        existing_tables = self.db.table_names()
        if table_name not in existing_tables:
            return []

        def _search() -> List[SearchResult]:
            table = self.db.open_table(table_name)
            results = (
                table.search(query_vector)
                .limit(top_k)
                .to_list()
            )
            out: List[SearchResult] = []
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
                ))
            return out

        return await asyncio.get_event_loop().run_in_executor(None, _search)
