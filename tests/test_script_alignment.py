"""
Tests for script alignment refactoring.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.exporters import export_graph_to_json, export_cypher_queries
from src.utils.diagnostics import GraphInspector


class TestScriptAlignment(unittest.TestCase):

    @patch("src.utils.exporters.Neo4jGraphClient")
    def test_export_graph_to_json(self, mock_client_cls):
        """Test that export logic calls Neo4j client correctly."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        # Mock data
        mock_client._execute_query.side_effect = [
            [{"id": "1", "labels": ["TestNode"], "properties": {"a": 1}}],  # Nodes
            [
                {"source_id": "1", "target_id": "2", "type": "LINK", "properties": {}}
            ],  # Rels
        ]
        mock_client.get_stats.return_value = {
            "nodes": 1,
            "edges": 1,
            "node_types": {},
            "relationship_types": {},
        }

        # Run export
        export_graph_to_json("test_export.json")

        # Verify
        assert mock_client._execute_query.call_count == 2
        mock_client.close.assert_called_once()

        # Clean up
        if os.path.exists("test_export.json"):
            os.remove("test_export.json")

    def test_export_cypher_queries(self):
        """Test cypher query export."""
        queries = export_cypher_queries("test_queries.json")
        assert "get_all_tables" in queries
        assert os.path.exists("test_queries.json")

        # Clean up
        os.remove("test_queries.json")

    @patch("src.utils.diagnostics.Neo4jGraphClient")
    def test_graph_inspector(self, mock_client_cls):
        """Test GraphInspector connection."""
        inspector = GraphInspector()
        mock_client_cls.return_value = MagicMock()

        assert inspector.connect() is True
        inspector.close()
        mock_client_cls.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
