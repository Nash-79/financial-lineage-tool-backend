"""Unit tests for Neo4j batch operations."""

import unittest
from unittest.mock import Mock, MagicMock, patch
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from neo4j.exceptions import TransientError


class TestNeo4jBatchOperations(unittest.TestCase):
    """Test Neo4j batch write operations."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Neo4j driver
        self.mock_driver = Mock()
        self.mock_session = Mock()
        self.mock_driver.session.return_value.__enter__ = Mock(
            return_value=self.mock_session
        )
        self.mock_driver.session.return_value.__exit__ = Mock(return_value=False)

        # Create client with mocked driver
        with patch(
            "src.knowledge_graph.neo4j_client.GraphDatabase.driver",
            return_value=self.mock_driver,
        ):
            self.client = Neo4jGraphClient(
                uri="bolt://localhost:7687", username="neo4j", password="password"
            )
            self.client.driver = self.mock_driver

    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self.client, "driver"):
            self.client.driver = None

    def test_batch_create_entities_empty_list(self):
        """Test batch entity creation with empty list."""
        result = self.client.batch_create_entities([])
        self.assertEqual(result, 0)

    def test_batch_create_entities_single_batch(self):
        """Test batch entity creation with single batch."""
        entities = [
            {"id": "t1", "entity_type": "Table", "name": "Users", "schema": "dbo"},
            {"id": "t2", "entity_type": "Table", "name": "Orders", "schema": "dbo"},
        ]

        # Mock successful transaction
        mock_result = [{"created": 2}]
        self.mock_session.execute_write.return_value = [
            Mock(data=lambda: r) for r in mock_result
        ]

        created = self.client.batch_create_entities(entities)

        self.assertEqual(created, 2)
        self.mock_session.execute_write.assert_called_once()

    def test_batch_create_entities_multiple_batches(self):
        """Test batch entity creation with multiple batches (>100 entities)."""
        # Create 250 entities
        entities = [
            {"id": f"t{i}", "entity_type": "Table", "name": f"Table{i}"}
            for i in range(250)
        ]

        # Mock successful transactions
        mock_result = [{"created": 100}]
        self.mock_session.execute_write.return_value = [
            Mock(data=lambda: r) for r in mock_result
        ]

        created = self.client.batch_create_entities(entities, batch_size=100)

        # Should create 3 batches (100 + 100 + 50)
        self.assertEqual(created, 300)  # 100 * 3 (mocked return value)
        self.assertEqual(self.mock_session.execute_write.call_count, 3)

    def test_batch_create_relationships_single_batch(self):
        """Test batch relationship creation with single batch."""
        relationships = [
            {"source_id": "t1", "target_id": "c1", "relationship_type": "CONTAINS"},
            {"source_id": "t2", "target_id": "c2", "relationship_type": "CONTAINS"},
        ]

        # Mock successful transaction
        mock_result = [{"created": 2}]
        self.mock_session.execute_write.return_value = [
            Mock(data=lambda: r) for r in mock_result
        ]

        created = self.client.batch_create_relationships(relationships)

        self.assertEqual(created, 2)
        self.mock_session.execute_write.assert_called_once()

    def test_batch_create_entities_with_retry_on_transient_error(self):
        """Test retry logic on transient Neo4j errors."""
        entities = [{"id": "t1", "entity_type": "Table", "name": "Users"}]

        # Mock transient error on first attempt, success on second
        mock_result = [{"created": 1}]
        self.mock_session.execute_write.side_effect = [
            TransientError("Connection timeout"),
            [Mock(data=lambda: r) for r in mock_result],
        ]

        with patch("time.sleep"):  # Skip actual sleep delays
            created = self.client.batch_create_entities(entities, max_retries=5)

        self.assertEqual(created, 1)
        self.assertEqual(self.mock_session.execute_write.call_count, 2)

    def test_batch_create_entities_exhausts_retries(self):
        """Test batch creation fails after exhausting retries."""
        entities = [{"id": "t1", "entity_type": "Table", "name": "Users"}]

        # Mock persistent transient errors
        self.mock_session.execute_write.side_effect = TransientError(
            "Connection timeout"
        )

        with patch("time.sleep"):  # Skip actual sleep delays
            with patch("src.knowledge_graph.neo4j_client.logger"):  # Suppress logs
                # Should attempt partial failure recovery
                with patch.object(
                    self.client, "_handle_partial_failure", return_value=0
                ):
                    created = self.client.batch_create_entities(entities, max_retries=3)

        self.assertEqual(created, 0)

    def test_split_into_batches(self):
        """Test batch splitting utility."""
        items = list(range(250))
        batches = self.client._split_into_batches(items, batch_size=100)

        self.assertEqual(len(batches), 3)
        self.assertEqual(len(batches[0]), 100)
        self.assertEqual(len(batches[1]), 100)
        self.assertEqual(len(batches[2]), 50)

    def test_execute_write_with_retry_exponential_backoff(self):
        """Test exponential backoff delays."""
        query = "CREATE (n:Test {id: $id})"
        params = {"id": "test1"}

        # Mock transient errors for 3 attempts
        mock_result = [{"created": 1}]
        self.mock_session.execute_write.side_effect = [
            TransientError("Timeout 1"),
            TransientError("Timeout 2"),
            [Mock(data=lambda: r) for r in mock_result],
        ]

        with patch("time.sleep") as mock_sleep:
            result = self.client._execute_write_with_retry(query, params, max_retries=5)

        # Verify exponential backoff: 1s, 2s
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    def test_handle_partial_failure_progressive_reduction(self):
        """Test partial failure recovery with progressive batch size reduction."""
        batch_data = [{"id": f"t{i}", "name": f"Table{i}"} for i in range(100)]
        query = "UNWIND $entities AS entity CREATE (n:Table) SET n = entity"

        # Mock failures for larger batches, success for size=10
        def mock_execute_write_side_effect(q, params, max_retries, batch_size):
            if batch_size > 10:
                raise TransientError("Batch too large")
            return [{"created": len(params.get("entities", []))}]

        with patch.object(
            self.client,
            "_execute_write_with_retry",
            side_effect=mock_execute_write_side_effect,
        ):
            with patch("src.knowledge_graph.neo4j_client.logger"):  # Suppress logs
                processed = self.client._handle_partial_failure(
                    query,
                    batch_data,
                    original_batch_size=100,
                    max_retries=5,
                    param_name="entities",
                )

        # Should successfully process all items at batch_size=10
        self.assertEqual(processed, 100)

    def test_log_failed_items(self):
        """Test failed item logging to JSONL."""
        import tempfile
        import os

        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        log_file = os.path.join(temp_dir, "failed_ingestion.jsonl")

        items = [{"id": "t1", "name": "Table1"}, {"id": "t2", "name": "Table2"}]

        # Patch Path in the neo4j_client module
        with patch("pathlib.Path") as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_class.return_value = mock_path_instance
            mock_path_instance.parent.mkdir = Mock()

            with patch("builtins.open", create=True) as mock_open:
                mock_file = MagicMock()
                mock_open.return_value.__enter__.return_value = mock_file

                self.client._log_failed_items(items, "Test error")

                # Verify file was written with 2 lines (one per item)
                self.assertEqual(mock_file.write.call_count, 2)
                # Verify mkdir was called
                mock_path_instance.parent.mkdir.assert_called_once_with(
                    parents=True, exist_ok=True
                )

        # Clean up
        import shutil

        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()
