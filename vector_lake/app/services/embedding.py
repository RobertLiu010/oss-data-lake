"""Embedding V5 API client."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import List

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Client for the Embedding V5 service (OpenAI-compatible).

    When EMBEDDING_MOCK=1 or the V5 service is unreachable,
    falls back to deterministic random vectors for testing.
    """

    def __init__(self, settings: Settings):
        self.base_url = settings.embedding.base_url.rstrip('/')
        self.model = settings.embedding.model
        self.dimension = settings.embedding.dimension
        self.task_passage = settings.embedding.task_passage
        self.task_query = settings.embedding.task_query
        self.batch_size = settings.embedding.batch_size
        self._mock = os.environ.get("EMBEDDING_MOCK", "").strip() == "1"

    # ------------------------------------------------------------------
    # Mock helper – deterministic pseudo-random vector from text hash
    # ------------------------------------------------------------------

    def _mock_vector(self, text: str) -> List[float]:
        """Generate a deterministic unit vector from text for testing."""
        h = hashlib.sha256(text.encode()).digest()
        import struct
        vals = []
        for i in range(0, min(len(h) * 2, self.dimension * 4), 4):
            chunk = h[i % len(h): i % len(h) + 4]
            if len(chunk) < 4:
                chunk = chunk + b'\x00' * (4 - len(chunk))
            vals.append(struct.unpack('<f', chunk)[0])
        # Extend or trim to dimension
        while len(vals) < self.dimension:
            vals.extend(vals[:min(len(vals), self.dimension - len(vals))])
        vec = vals[:self.dimension]
        # L2 normalize
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    async def _embed(self, texts: List[str], task: str) -> List[List[float]]:
        """Call POST /v1/embeddings and return embedding vectors."""
        if self._mock:
            return [self._mock_vector(t) for t in texts]

        all_vectors: List[List[float]] = []

        async with httpx.AsyncClient(timeout=300.0) as client:
            for offset in range(0, len(texts), self.batch_size):
                batch = texts[offset:offset + self.batch_size]
                payload = {
                    "model": self.model,
                    "task": task,
                    "input": batch,
                    "dimensions": self.dimension,
                }
                resp = await client.post(
                    f"{self.base_url}/v1/embeddings",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                # Sort by index to guarantee order
                sorted_data = sorted(data["data"], key=lambda d: d["index"])
                for item in sorted_data:
                    all_vectors.append(item["embedding"])

        return all_vectors

    async def embed_passages(self, texts: List[str]) -> List[List[float]]:
        """Embed documents with task=retrieval.passage."""
        if not texts:
            return []
        logger.info("Embedding %d passages", len(texts))
        return await self._embed(texts, self.task_passage)

    async def embed_query(self, text: str) -> List[float]:
        """Embed query with task=retrieval.query."""
        logger.info("Embedding query: %s", text[:80])
        vectors = await self._embed([text], self.task_query)
        return vectors[0]
