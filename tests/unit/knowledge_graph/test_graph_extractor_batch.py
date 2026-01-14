"""Unit tests for GraphExtractor batch operations."""

import unittest
from unittest.mock import Mock
from src.knowledge_graph.entity_extractor import GraphExtractor
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.ingestion.code_parser import CodeParser


class TestGraphExtractorBatch(unittest.TestCase):
    """Test GraphExtractor batch processing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Neo4j client
        self.mock_client = Mock(spec=Neo4jGraphClient)
        self.mock_client.batch_create_entities.return_value = 0
        self.mock_client.batch_create_relationships.return_value = 0

        # Mock code parser
        self.mock_parser = Mock(spec=CodeParser)

        # Create extractor with batching enabled
        self.extractor = GraphExtractor(
            neo4j_client=self.mock_client,
            code_parser=self.mock_parser,
            enable_batching=True,
            batch_size=3,  # Small batch size for testing
        )

    def test_add_entity_to_batch_accumulates(self):
        """Test entities accumulate in batch."""
        self.extractor._add_entity_to_batch("e1", "Table", name="Table1")
        self.extractor._add_entity_to_batch("e2", "Table", name="Table2")

        self.assertEqual(len(self.extractor._entity_batch), 2)
        self.assertEqual(self.extractor._entity_batch[0]["id"], "e1")
        self.assertEqual(self.extractor._entity_batch[1]["id"], "e2")

    def test_add_entity_to_batch_auto_flush(self):
        """Test auto-flush when batch size reached."""
        # Add 3 entities (batch_size=3)
        self.extractor._add_entity_to_batch("e1", "Table", name="Table1")
        self.extractor._add_entity_to_batch("e2", "Table", name="Table2")
        self.extractor._add_entity_to_batch("e3", "Table", name="Table3")

        # Should trigger auto-flush
        self.mock_client.batch_create_entities.assert_called_once()
        # Batch should be cleared after flush
        self.assertEqual(len(self.extractor._entity_batch), 0)

    def test_add_relationship_to_batch_accumulates(self):
        """Test relationships accumulate in batch."""
        self.extractor._add_relationship_to_batch("e1", "e2", "CONTAINS")
        self.extractor._add_relationship_to_batch("e2", "e3", "REFERENCES")

        self.assertEqual(len(self.extractor._relationship_batch), 2)
        self.assertEqual(self.extractor._relationship_batch[0]["source_id"], "e1")
        self.assertEqual(
            self.extractor._relationship_batch[1]["relationship_type"], "REFERENCES"
        )

    def test_add_relationship_to_batch_auto_flush(self):
        """Test auto-flush for relationships when batch size reached."""
        # Add 3 relationships (batch_size=3)
        self.extractor._add_relationship_to_batch("e1", "e2", "REL1")
        self.extractor._add_relationship_to_batch("e2", "e3", "REL2")
        self.extractor._add_relationship_to_batch("e3", "e4", "REL3")

        # Should trigger auto-flush
        self.mock_client.batch_create_relationships.assert_called_once()
        # Batch should be cleared after flush
        self.assertEqual(len(self.extractor._relationship_batch), 0)

    def test_flush_batch_flushes_both_types(self):
        """Test manual flush writes both entities and relationships."""
        # Add some items
        self.extractor._add_entity_to_batch("e1", "Table", name="Table1")
        self.extractor._add_relationship_to_batch("e1", "e2", "CONTAINS")

        # Manual flush
        self.extractor.flush_batch()

        # Both should be flushed
        self.mock_client.batch_create_entities.assert_called_once()
        self.mock_client.batch_create_relationships.assert_called_once()

        # Batches should be empty
        self.assertEqual(len(self.extractor._entity_batch), 0)
        self.assertEqual(len(self.extractor._relationship_batch), 0)

    def test_flush_batch_empty_batches(self):
        """Test flush with empty batches doesn't call client."""
        self.extractor.flush_batch()

        # Should not call client methods
        self.mock_client.batch_create_entities.assert_not_called()
        self.mock_client.batch_create_relationships.assert_not_called()

    def test_batching_disabled_writes_immediately(self):
        """Test entities written immediately when batching disabled."""
        extractor = GraphExtractor(
            neo4j_client=self.mock_client,
            code_parser=self.mock_parser,
            enable_batching=False,
        )

        extractor._add_entity_to_batch("e1", "Table", name="Table1")

        # Should call add_entity directly, not batch
        self.mock_client.add_entity.assert_called_once_with(
            entity_id="e1", entity_type="Table", name="Table1"
        )

        # Batch should remain empty
        self.assertEqual(len(extractor._entity_batch), 0)

    def test_ingest_sql_lineage_uses_batching(self):
        """Test SQL lineage ingestion uses batch methods."""
        # Mock parsed data
        self.mock_parser.parse_sql.return_value = {
            "write": "target_table",
            "read": ["source_table"],
            "views": [],
            "columns": [],
            "functions_and_procedures": [],
        }

        self.extractor.ingest_sql_lineage(
            "SELECT * FROM source_table", source_file="test.sql"
        )

        # Should have accumulated entities (not flushed automatically)
        self.assertGreater(len(self.extractor._entity_batch), 0)

    def test_ingest_sql_lineage_with_column_lineage(self):
        """Test SQL lineage with column-level transformations."""
        # Mock parsed data with column lineage
        self.mock_parser.parse_sql.return_value = {
            "write": "target_table",
            "read": ["source_table"],
            "views": [],
            "columns": [
                {
                    "target": "total_amount",
                    "transformation": "quantity * price",
                    "sources": ["source_table.quantity", "source_table.price"],
                }
            ],
            "functions_and_procedures": [],
        }

        self.extractor.ingest_sql_lineage(
            "SELECT * FROM source_table", source_file="test.sql"
        )

        # Column lineage creates many entities (source table, target table, columns, transformations)
        # With batch_size=3, this should trigger auto-flush
        # Verify batch operations were called
        self.assertGreater(self.mock_client.batch_create_entities.call_count, 0)
        self.assertGreater(self.mock_client.batch_create_relationships.call_count, 0)

    def test_flush_entities_clears_batch_on_error(self):
        """Test entity batch is cleared even if flush fails."""
        self.extractor._add_entity_to_batch("e1", "Table", name="Table1")

        # Mock batch_create_entities to raise exception
        self.mock_client.batch_create_entities.side_effect = Exception("Neo4j error")

        with self.assertRaises(Exception):
            self.extractor._flush_entities()

        # Batch should be cleared despite error
        self.assertEqual(len(self.extractor._entity_batch), 0)

    def test_flush_relationships_clears_batch_on_error(self):
        """Test relationship batch is cleared even if flush fails."""
        self.extractor._add_relationship_to_batch("e1", "e2", "CONTAINS")

        # Mock batch_create_relationships to raise exception
        self.mock_client.batch_create_relationships.side_effect = Exception(
            "Neo4j error"
        )

        with self.assertRaises(Exception):
            self.extractor._flush_relationships()

        # Batch should be cleared despite error
        self.assertEqual(len(self.extractor._relationship_batch), 0)

    def test_ingest_python_uses_batching(self):
        """Test Python ingestion uses batch methods."""
        # Mock parsed Python data
        self.mock_parser.parse_python.return_value = {
            "classes": [{"name": "TestClass", "bases": [], "docstring": "Test"}],
            "functions": [{"name": "test_func", "args": [], "docstring": "Test"}],
            "imports": ["os", "sys"],
        }

        self.extractor.ingest_python("class TestClass: pass", source_file="test.py")

        # Should have accumulated entities
        self.assertGreater(len(self.extractor._entity_batch), 0)

    def test_ingest_json_uses_batching(self):
        """Test JSON ingestion uses batch methods."""
        # Mock parsed JSON data with enough keys to trigger relationship flush
        self.mock_parser.parse_json.return_value = {
            "type": "object",
            "keys": ["key1", "key2", "key3", "key4"],  # 4 keys to ensure flush
            "array_length": 0,
        }

        self.extractor.ingest_json('{"key1": "value1"}', source_file="test.json")

        # JSON ingestion creates: 1 JsonDocument + 4 JsonKey entities + 4 HAS_KEY relationships
        # With batch_size=3, both entities and relationships should trigger auto-flush
        # Verify batch operations were called
        self.assertGreater(self.mock_client.batch_create_entities.call_count, 0)
        self.assertGreater(self.mock_client.batch_create_relationships.call_count, 0)

    def test_batch_size_configuration(self):
        """Test custom batch size configuration."""
        extractor = GraphExtractor(
            neo4j_client=self.mock_client,
            code_parser=self.mock_parser,
            enable_batching=True,
            batch_size=5,
        )

        # Add 4 entities (less than batch size)
        for i in range(4):
            extractor._add_entity_to_batch(f"e{i}", "Table", name=f"Table{i}")

        # Should not flush yet
        self.mock_client.batch_create_entities.assert_not_called()

        # Add 5th entity (reaches batch size)
        extractor._add_entity_to_batch("e5", "Table", name="Table5")

        # Should flush now
        self.mock_client.batch_create_entities.assert_called_once()


if __name__ == "__main__":
    unittest.main()
