"""Qdrant vector database service client."""

from __future__ import annotations

from typing import Optional

import httpx


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

    async def create_collection(
        self, name: str, vector_size: int = 768  # nomic-embed-text dimension
    ):
        """Create a vector collection.

        Args:
            name: Collection name.
            vector_size: Dimension of embedding vectors (default: 768).

        Returns:
            Response JSON from Qdrant.
        """
        response = await self.client.put(
            f"{self.base_url}/collections/{name}",
            json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        )
        return response.json()

    async def upsert(self, collection: str, points: list[dict]):
        """Upsert vectors into collection.

        Inserts new vectors or updates existing ones based on point IDs.

        Args:
            collection: Collection name.
            points: List of point objects with id, vector, and payload.

        Returns:
            Response JSON from Qdrant.
        """
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
        payload = {"vector": vector, "limit": limit, "with_payload": True}

        if filter_conditions:
            payload["filter"] = filter_conditions

        response = await self.client.post(
            f"{self.base_url}/collections/{collection}/points/search", json=payload
        )

        return response.json().get("result", [])

    async def close(self):
        """Close the HTTP client and cleanup resources."""
        await self.client.aclose()
