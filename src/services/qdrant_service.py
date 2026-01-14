"""Qdrant vector database service client."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


_SPARSE_DIM = 2**18
_BM25_K1 = 1.5
_BM25_B = 0.75


class QdrantLocalClient:
    """Client for local Qdrant vector database.

    Provides methods for creating collections, upserting vectors, and
    performing similarity search operations.

    Attributes:
        base_url: Qdrant server base URL.
        client: Async HTTP client for API requests.
    """

    def __init__(self, host: str, port: int):
        """Initialize Qdrant client.

        Args:
            host: Qdrant server hostname.
            port: Qdrant server port.
        """
        self.base_url = f"http://{host}:{port}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self._collection_cache: Dict[str, Dict[str, Any]] = {}

    async def create_collection(
        self,
        name: str,
        vector_size: int = 768,  # nomic-embed-text dimension
        ef_construct: int | None = None,
        m: int | None = None,
        enable_hybrid: bool = True,
    ):
        """Create a vector collection.

        Args:
            name: Collection name.
            vector_size: Dimension of embedding vectors (default: 768).
            ef_construct: HNSW ef_construct parameter (higher -> better recall, slower build).
            m: HNSW M parameter (graph degree).

        Returns:
            Response JSON from Qdrant.
        """
        hnsw_config = {}
        if ef_construct is not None:
            hnsw_config["ef_construct"] = ef_construct
        if m is not None:
            hnsw_config["m"] = m

        if enable_hybrid:
            payload = {
                "vectors": {
                    "dense": {"size": vector_size, "distance": "Cosine"},
                },
                "sparse_vectors": {
                    "sparse": {"index": {}},
                },
            }
        else:
            payload = {"vectors": {"size": vector_size, "distance": "Cosine"}}
        if hnsw_config:
            payload["hnsw_config"] = hnsw_config

        response = await self.client.put(
            f"{self.base_url}/collections/{name}",
            json=payload,
        )
        self._collection_cache.pop(name, None)
        return response.json()

    async def collection_info(self, name: str) -> dict:
        """Fetch collection info including HNSW settings and vector count."""
        response = await self.client.get(f"{self.base_url}/collections/{name}")
        return response.json()

    async def _get_collection_config(self, name: str) -> Dict[str, Any]:
        if name in self._collection_cache:
            return self._collection_cache[name]
        info = await self.collection_info(name)
        params = info.get("result", {}).get("config", {}).get("params", {})
        vectors = params.get("vectors", {})
        sparse_vectors = params.get("sparse_vectors", {})
        named_vectors = isinstance(vectors, dict) and not (
            "size" in vectors and "distance" in vectors
        )
        config = {
            "named_vectors": bool(named_vectors),
            "supports_sparse": bool(sparse_vectors),
        }
        self._collection_cache[name] = config
        return config

    async def upsert(self, collection: str, points: list[dict]):
        """Upsert vectors into collection.

        Inserts new vectors or updates existing ones based on point IDs.

        Args:
            collection: Collection name.
            points: List of point objects with id, vector, and payload.

        Returns:
            Response JSON from Qdrant.
        """
        config = await self._get_collection_config(collection)
        if config["named_vectors"]:
            for point in points:
                if "vectors" in point:
                    continue
                vector = point.pop("vector", None)
                if vector is None:
                    continue
                vectors: Dict[str, Any] = {"dense": vector}
                sparse = point.pop("sparse_vector", None)
                if config.get("supports_sparse") and sparse is not None:
                    vectors["sparse"] = sparse
                point["vectors"] = vectors

        response = await self.client.put(
            f"{self.base_url}/collections/{collection}/points", json={"points": points}
        )
        return response.json()

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int = 10,
        filter_conditions: Optional[dict] = None,
    ) -> list[dict]:
        """Search for similar vectors.

        Performs cosine similarity search to find nearest neighbors.

        Args:
            collection: Collection name.
            vector: Query vector.
            limit: Maximum number of results.
            filter_conditions: Optional filter criteria for metadata.

        Returns:
            List of search results with scores and payloads.
        """
        config = await self._get_collection_config(collection)
        if config["named_vectors"]:
            vector_payload: Any = {"name": "dense", "vector": vector}
        else:
            vector_payload = vector

        payload = {"vector": vector_payload, "limit": limit, "with_payload": True}

        if filter_conditions:
            payload["filter"] = filter_conditions

        response = await self.client.post(
            f"{self.base_url}/collections/{collection}/points/search", json=payload
        )

        return response.json().get("result", [])

    async def search_sparse(
        self,
        collection: str,
        query_text: str,
        limit: int = 10,
        filter_conditions: Optional[dict] = None,
    ) -> list[dict]:
        """Search using sparse vectors derived from query text."""
        config = await self._get_collection_config(collection)
        if not config.get("supports_sparse"):
            return []

        sparse_vector = self.build_sparse_vector(query_text)
        payload = {
            "sparse_vector": {"name": "sparse", "vector": sparse_vector},
            "limit": limit,
            "with_payload": True,
        }
        if filter_conditions:
            payload["filter"] = filter_conditions

        response = await self.client.post(
            f"{self.base_url}/collections/{collection}/points/search",
            json=payload,
        )
        return response.json().get("result", [])

    async def hybrid_search(
        self,
        collection: str,
        *,
        query_text: str,
        dense_vector: list[float],
        limit: int = 10,
        filter_conditions: Optional[dict] = None,
        fusion_weight: float = 0.5,
    ) -> list[dict]:
        """Hybrid search combining sparse + dense results with RRF."""
        sparse_limit = limit * 2
        dense_limit = limit * 2

        sparse_task = self.search_sparse(
            collection,
            query_text,
            limit=sparse_limit,
            filter_conditions=filter_conditions,
        )
        dense_task = self.search(
            collection,
            dense_vector,
            limit=dense_limit,
            filter_conditions=filter_conditions,
        )

        sparse_results, dense_results = await asyncio.gather(
            sparse_task, dense_task, return_exceptions=False
        )

        return self._fuse_results(
            sparse_results, dense_results, limit=limit, fusion_weight=fusion_weight
        )

    def build_sparse_vector(self, text: str) -> Dict[str, list]:
        """Create a sparse vector from text using BM25-like weighting."""
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        if not tokens:
            return {"indices": [], "values": []}

        term_counts: Dict[str, int] = {}
        for token in tokens:
            term_counts[token] = term_counts.get(token, 0) + 1

        doc_len = len(tokens)
        avg_len = max(1, doc_len)

        indices = []
        values = []
        for term, freq in term_counts.items():
            term_hash = hashlib.md5(term.encode("utf-8")).hexdigest()
            idx = int(term_hash, 16) % _SPARSE_DIM
            norm = freq + _BM25_K1 * (1 - _BM25_B + _BM25_B * (doc_len / avg_len))
            weight = (freq * (_BM25_K1 + 1)) / norm
            indices.append(idx)
            values.append(weight)

        paired = sorted(zip(indices, values), key=lambda x: x[0])
        indices_sorted, values_sorted = zip(*paired)
        return {"indices": list(indices_sorted), "values": list(values_sorted)}

    async def build_vectors_payload(
        self,
        collection: str,
        dense_vector: list[float],
        sparse_vector: Optional[Dict[str, list]] = None,
    ) -> Dict[str, Any]:
        """Build vector payload for upsert based on collection capabilities."""
        config = await self._get_collection_config(collection)
        if config["named_vectors"]:
            vectors: Dict[str, Any] = {"dense": dense_vector}
            if config.get("supports_sparse") and sparse_vector:
                vectors["sparse"] = sparse_vector
            return {"vectors": vectors}
        return {"vector": dense_vector}

    def _fuse_results(
        self,
        sparse_results: list[dict],
        dense_results: list[dict],
        *,
        limit: int,
        fusion_weight: float,
        rrf_k: int = 60,
    ) -> list[dict]:
        """Fuse sparse and dense results with Reciprocal Rank Fusion."""
        scores: Dict[Any, Dict[str, Any]] = {}

        def add_scores(results: list[dict], weight: float) -> None:
            for rank, item in enumerate(results, start=1):
                item_id = item.get("id")
                if item_id is None:
                    continue
                rrf_score = 1.0 / (rrf_k + rank)
                entry = scores.setdefault(item_id, {"item": item, "score": 0.0})
                entry["score"] += weight * rrf_score

        add_scores(sparse_results, 1.0 - fusion_weight)
        add_scores(dense_results, fusion_weight)

        fused = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        return [entry["item"] for entry in fused[:limit]]

    async def delete_by_file_path(
        self,
        collection: str,
        file_path: str,
        project_id: Optional[str] = None,
        repository_id: Optional[str] = None,
    ) -> dict:
        """Delete all points matching a file path (optionally scoped)."""
        must = [{"key": "file_path", "match": {"value": file_path}}]
        if project_id:
            must.append({"key": "project_id", "match": {"value": project_id}})
        if repository_id:
            must.append({"key": "repository_id", "match": {"value": repository_id}})
        filter_payload = {"filter": {"must": must}}
        count_response = await self.client.post(
            f"{self.base_url}/collections/{collection}/points/count",
            json={**filter_payload, "exact": True},
        )
        count_response.raise_for_status()
        deleted_count = count_response.json().get("result", {}).get("count", 0)

        response = await self.client.post(
            f"{self.base_url}/collections/{collection}/points/delete",
            params={"wait": "true"},
            json=filter_payload,
        )
        response.raise_for_status()
        result = response.json()
        result["deleted"] = deleted_count
        return result

    async def get_point(
        self, collection: str, point_id: str | int
    ) -> Optional[dict]:
        """Fetch a single point by ID."""
        resolved_id: str | int = point_id
        if isinstance(point_id, str) and point_id.isdigit():
            resolved_id = int(point_id)

        response = await self.client.post(
            f"{self.base_url}/collections/{collection}/points",
            json={"ids": [resolved_id], "with_payload": True},
        )
        response.raise_for_status()
        points = response.json().get("result", [])
        return points[0] if points else None

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        await self.client.aclose()
