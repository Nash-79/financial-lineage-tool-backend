"""
Tests for API Endpoints

Run with: pytest tests/test_api_endpoints.py -v
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    # Import here to avoid issues with module loading
    from src.api.main_local import app

    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_200(self, client):
        """Health check should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_structure(self, client):
        """Health check should return proper structure."""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert "services" in data
        assert "timestamp" in data

    def test_health_check_includes_services(self, client):
        """Health check should include service statuses."""
        response = client.get("/health")
        data = response.json()
        services = data["services"]

        assert "api" in services
        assert "ollama" in services
        assert "qdrant" in services
        assert "neo4j" in services
        assert "rag_mode" in services


class TestChatEndpoints:
    """Test chat endpoints."""

    def test_chat_deep_requires_query(self, client):
        """Chat deep endpoint should require query."""
        response = client.post("/api/chat/deep", json={})
        # Should fail validation (422) without query
        assert response.status_code == 422

    def test_chat_deep_with_query(self, client):
        """Chat deep endpoint should accept valid query."""
        response = client.post("/api/chat/deep", json={"query": "test query"})
        # May return 500/503 if services not available, but should not be 404
        assert response.status_code != 404

    def test_chat_semantic_endpoint_exists(self, client):
        """Chat semantic endpoint should exist."""
        response = client.post("/api/chat/semantic", json={"query": "test"})
        assert response.status_code != 404

    def test_chat_graph_endpoint_exists(self, client):
        """Chat graph endpoint should exist."""
        response = client.post("/api/chat/graph", json={"query": "test"})
        assert response.status_code != 404

    def test_chat_text_endpoint_exists(self, client):
        """Chat text endpoint should exist."""
        response = client.post("/api/chat/text", json={"query": "test"})
        assert response.status_code != 404


class TestLineageEndpoints:
    """Test lineage endpoints."""

    def test_lineage_nodes_endpoint(self, client):
        """Lineage nodes endpoint should exist."""
        response = client.get("/api/v1/lineage/nodes")
        # Should return 200 or 503 (if Neo4j unavailable), not 404
        assert response.status_code in [200, 503]

    def test_lineage_edges_endpoint(self, client):
        """Lineage edges endpoint should exist."""
        response = client.get("/api/v1/lineage/edges")
        assert response.status_code in [200, 503]

    def test_lineage_search_endpoint(self, client):
        """Lineage search endpoint should exist."""
        response = client.get("/api/v1/lineage/search?q=test")
        assert response.status_code != 404

    def test_lineage_node_detail_endpoint(self, client):
        """Lineage node detail endpoint should exist."""
        response = client.get("/api/v1/lineage/node/test-id")
        # May return 404 for non-existent node, or 500/503 for service issues
        assert response.status_code in [200, 404, 500, 503]

    def test_lineage_edges_filters_endpoint(self, client):
        """Lineage edges endpoint should accept filter parameters."""
        response = client.get(
            "/api/v1/lineage/edges?status=approved&min_confidence=0.5&source=parser"
        )
        assert response.status_code in [200, 503]

    def test_lineage_review_endpoint(self, client):
        """Lineage review endpoint should exist."""
        payload = {
            "source_id": "test-source",
            "target_id": "test-target",
            "relationship_type": "READS_FROM",
            "action": "approve",
        }
        response = client.post("/api/v1/lineage/review", json=payload)
        assert response.status_code in [200, 503]

    def test_lineage_infer_endpoint(self, client):
        """Lineage inference endpoint should exist."""
        payload = {"scope": "test-scope"}
        response = client.post("/api/v1/lineage/infer", json=payload)
        assert response.status_code in [200, 503]


class TestFileEndpoints:
    """Test file endpoints."""

    def test_files_list_endpoint(self, client):
        """Files list endpoint should exist."""
        response = client.get("/api/v1/files")
        assert response.status_code == 200

    def test_files_recent_endpoint(self, client):
        """Recent files endpoint should exist."""
        response = client.get("/api/v1/files/recent")
        assert response.status_code == 200

    def test_files_stats_endpoint(self, client):
        """File stats endpoint should exist."""
        response = client.get("/api/v1/files/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data

    def test_files_search_endpoint(self, client):
        """File search endpoint should exist."""
        response = client.get("/api/v1/files/search?q=test")
        assert response.status_code == 200


class TestQdrantEndpoints:
    """Test Qdrant lookup endpoints."""

    def test_qdrant_chunk_lookup_endpoint(self, client):
        """Qdrant chunk lookup endpoint should exist."""
        response = client.get("/api/v1/qdrant/chunks/123")
        assert response.status_code in [200, 404, 503]


class TestDatabaseEndpoints:
    """Test database-related endpoints."""

    def test_database_schemas_endpoint(self, client):
        """Database schemas endpoint should exist."""
        response = client.get("/api/database/schemas")
        # Should return 200 or 503 (if Neo4j unavailable)
        assert response.status_code in [200, 503]

    def test_stats_endpoint(self, client):
        """Stats endpoint should exist."""
        response = client.get("/api/v1/stats")
        # Should return 200 or 503
        assert response.status_code in [200, 503]


class TestActivityEndpoints:
    """Test activity and monitoring endpoints."""

    def test_activity_recent_endpoint(self, client):
        """Recent activity endpoint should exist."""
        response = client.get("/api/v1/activity/recent")
        assert response.status_code == 200

    def test_rag_status_endpoint(self, client):
        """RAG status endpoint should exist."""
        response = client.get("/api/v1/rag/status")
        assert response.status_code == 200
        data = response.json()

        assert "mode" in data
        assert "total_queries" in data
        assert "status" in data


class TestAdminEndpoints:
    """Test admin endpoints."""

    def test_admin_restart_endpoint_exists(self, client):
        """Admin restart endpoint should exist."""
        # Don't actually restart, just check endpoint exists
        # We use OPTIONS to check without triggering restart
        response = client.options("/admin/restart")
        # OPTIONS may not be allowed (405), but endpoint exists (not 404)
        assert response.status_code != 404


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    def test_openapi_schema(self, client):
        """OpenAPI schema should be accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    def test_swagger_ui(self, client):
        """Swagger UI should be accessible."""
        response = client.get("/docs")
        assert response.status_code == 200


# Integration tests (require services)
class TestIntegration:
    """Integration tests that require running services."""

    @pytest.mark.integration
    def test_full_chat_flow(self, client):
        """Test complete chat flow if services are available."""
        # Check health first
        health = client.get("/health")
        if health.status_code != 200:
            pytest.skip("Services not available")

        # Try chat endpoint
        response = client.post(
            "/api/chat/text", json={"query": "What is data lineage?"}
        )

        if response.status_code == 200:
            data = response.json()
            assert "response" in data
            assert "query_type" in data
            assert data["query_type"] == "text"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
