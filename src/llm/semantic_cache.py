"""
Semantic query cache with optional Qdrant backend.

Stores query embeddings and responses, enabling similarity-based reuse
for repeated or near-duplicate questions.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional


class SemanticQueryCache:
    """Semantic cache with optional vector-store backing."""

    def __init__(
        self,
        qdrant_client: Any = None,
        collection_name: str = "query_cache",
        dim: int = 768,
        threshold: float = 0.95,
    ):
        self.qdrant = qdrant_client
        self.collection = collection_name
        self.dim = dim
        self.threshold = threshold
        self._memory_cache: List[tuple[list[float], Dict[str, Any]]] = []

        if self.qdrant:
            self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create collection in Qdrant if missing."""
        try:
            from qdrant_client.http import models as rest

            if self.collection not in self.qdrant.get_collections().collections:
                self.qdrant.recreate_collection(
                    collection_name=self.collection,
                    vectors_config=rest.VectorParams(
                        size=self.dim, distance=rest.Distance.COSINE
                    ),
                )
        except Exception:
            # Fail silently; fallback to in-memory cache
            self.qdrant = None

    def search(self, embedding: list[float]) -> Optional[Dict[str, Any]]:
        """Search for a cached response with similarity above threshold."""
        if self.qdrant:
            try:
                results = self.qdrant.search(
                    collection_name=self.collection,
                    query_vector=embedding,
                    limit=1,
                    score_threshold=self.threshold,
                )
                if results:
                    payload = results[0].payload or {}
                    return payload if payload else None
            except Exception:
                pass

        # Fallback to in-memory cosine search
        best = None
        best_score = -1.0
        for vec, payload in self._memory_cache:
            score = self._cosine_similarity(embedding, vec)
            if score >= self.threshold and score > best_score:
                best = payload
                best_score = score
        return best

    def upsert(self, embedding: list[float], payload: Dict[str, Any]) -> None:
        """Store embedding + payload in cache."""
        if self.qdrant:
            try:
                from qdrant_client.http import models as rest

                self.qdrant.upsert(
                    collection_name=self.collection,
                    points=[
                        rest.PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload=payload,
                        )
                    ],
                )
                return
            except Exception:
                pass

        # Fallback: append to in-memory cache
        self._memory_cache.append((embedding, payload))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
