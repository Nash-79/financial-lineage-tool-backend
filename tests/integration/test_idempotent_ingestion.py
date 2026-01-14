"""Integration test for purge-then-write idempotency."""

from __future__ import annotations

import os
import uuid

import httpx
import pytest
from dotenv import load_dotenv

from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.services.ingestion_pipeline import purge_before_ingest
from src.services.qdrant_service import QdrantLocalClient
from src.utils.urn import generate_urn


load_dotenv()


def _neo4j_config() -> tuple[str, str, str, str]:
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    return uri, username, password, database


def _qdrant_host_port() -> tuple[str, int]:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return host, port


async def _count_qdrant_points(
    client: QdrantLocalClient,
    collection: str,
    file_path: str,
    project_id: str,
) -> int:
    payload = {
        "filter": {
            "must": [
                {"key": "file_path", "match": {"value": file_path}},
                {"key": "project_id", "match": {"value": project_id}},
            ]
        },
        "exact": True,
    }
    response = await client.client.post(
        f"{client.base_url}/collections/{collection}/points/count",
        json=payload,
    )
    response.raise_for_status()
    return response.json().get("result", {}).get("count", 0)


def _count_neo4j_nodes(
    graph: Neo4jGraphClient,
    file_path: str,
    project_id: str,
) -> int:
    records = graph._execute_query(
        """
        MATCH (n)
        WHERE n.source_file = $file_path AND n.project_id = $project_id
        RETURN count(n) AS count
        """,
        {"file_path": file_path, "project_id": project_id},
    )
    if not records:
        return 0
    return int(records[0].get("count", 0))


@pytest.mark.asyncio
async def test_purge_then_write_idempotency():
    uri, username, password, database = _neo4j_config()
    if not uri or not username or not password:
        pytest.skip("Neo4j credentials not configured for idempotency test")

    host, port = _qdrant_host_port()
    qdrant = QdrantLocalClient(host, port)
    collection = f"test_idempotency_{uuid.uuid4().hex[:8]}"
    graph = None

    try:
        try:
            resp = await qdrant.client.get(f"{qdrant.base_url}/collections")
            resp.raise_for_status()
        except httpx.HTTPError:
            pytest.skip("Qdrant not available for idempotency integration test")

        graph = Neo4jGraphClient(
            uri=uri, username=username, password=password, database=database
        )

        await qdrant.create_collection(collection, vector_size=3, enable_hybrid=True)

        file_path = "integration/idempotency.sql"
        project_id = "integration-test"

        node_a = generate_urn("Table", project_id, "alpha")
        node_b = generate_urn("Table", project_id, "beta")

        graph.add_entity(
            entity_id=node_a,
            entity_type="Table",
            name="alpha",
            source_file=file_path,
            project_id=project_id,
        )
        graph.add_entity(
            entity_id=node_b,
            entity_type="Table",
            name="beta",
            source_file=file_path,
            project_id=project_id,
        )
        graph.add_relationship(
            source_id=node_a,
            target_id=node_b,
            relationship_type="READS",
            source_file=file_path,
            project_id=project_id,
        )

        await qdrant.upsert(
            collection,
            points=[
                {
                    "id": 1,
                    "vector": [1.0, 0.0, 0.0],
                    "sparse_vector": qdrant.build_sparse_vector("alpha"),
                    "payload": {"file_path": file_path, "project_id": project_id},
                },
                {
                    "id": 2,
                    "vector": [0.0, 1.0, 0.0],
                    "sparse_vector": qdrant.build_sparse_vector("beta"),
                    "payload": {"file_path": file_path, "project_id": project_id},
                },
            ],
        )

        assert _count_neo4j_nodes(graph, file_path, project_id) == 2
        assert (
            await _count_qdrant_points(qdrant, collection, file_path, project_id) == 2
        )

        class State:
            pass

        state = State()
        state.qdrant = qdrant
        state.graph = graph

        await purge_before_ingest(
            file_path=file_path,
            state=state,
            project_id=project_id,
            collection=collection,
        )

        assert _count_neo4j_nodes(graph, file_path, project_id) == 0
        assert (
            await _count_qdrant_points(qdrant, collection, file_path, project_id) == 0
        )

        graph.add_entity(
            entity_id=node_a,
            entity_type="Table",
            name="alpha",
            source_file=file_path,
            project_id=project_id,
        )

        await qdrant.upsert(
            collection,
            points=[
                {
                    "id": 3,
                    "vector": [0.5, 0.5, 0.0],
                    "sparse_vector": qdrant.build_sparse_vector("alpha"),
                    "payload": {"file_path": file_path, "project_id": project_id},
                }
            ],
        )

        assert _count_neo4j_nodes(graph, file_path, project_id) == 1
        assert (
            await _count_qdrant_points(qdrant, collection, file_path, project_id) == 1
        )
    finally:
        try:
            if graph:
                graph.purge_file_assets(
                    file_path="integration/idempotency.sql",
                    project_id="integration-test",
                )
                graph.close()
        except Exception:
            pass
        try:
            await qdrant.client.delete(f"{qdrant.base_url}/collections/{collection}")
        except Exception:
            pass
        await qdrant.client.aclose()
