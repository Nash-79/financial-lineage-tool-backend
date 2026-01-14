"""Unit tests for ParseCache."""

import os
import tempfile
import unittest

from src.ingestion.parse_cache import ParseCache


class TestParseCache(unittest.TestCase):
    """Test ParseCache functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for cache
        self.temp_dir = tempfile.mkdtemp()
        self.cache_path = os.path.join(self.temp_dir, "test_cache.db")
        self.cache = ParseCache(cache_path=self.cache_path, max_entries=10, ttl_days=1)

        # Create temporary SQL file for testing
        self.test_file = os.path.join(self.temp_dir, "test.sql")
        with open(self.test_file, "w") as f:
            f.write("SELECT * FROM test_table;")

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_cache_miss(self):
        """Test cache miss returns None."""
        result = self.cache.get(self.test_file)
        self.assertIsNone(result)
        self.assertEqual(self.cache._misses, 1)
        self.assertEqual(self.cache._hits, 0)

    def test_cache_hit(self):
        """Test cache hit returns cached value."""
        # Store value
        test_data = {"objects": [], "object_map": {}}
        self.cache.set(self.test_file, test_data)

        # Retrieve value
        result = self.cache.get(self.test_file)
        self.assertIsNotNone(result)
        self.assertEqual(result, test_data)
        self.assertEqual(self.cache._hits, 1)

    def test_cache_invalidation_on_file_change(self):
        """Test cache invalidates when file content changes."""
        # Store value with original content
        test_data = {"test": "data"}
        self.cache.set(self.test_file, test_data)

        # Verify cache hit
        result = self.cache.get(self.test_file)
        self.assertEqual(result, test_data)

        # Modify file content
        with open(self.test_file, "w") as f:
            f.write("SELECT * FROM different_table;")

        # Should be cache miss now (different hash)
        result = self.cache.get(self.test_file)
        self.assertIsNone(result)

    def test_cache_eviction_lru(self):
        """Test LRU eviction when max_entries exceeded."""
        # Create cache with max 3 entries
        cache = ParseCache(
            cache_path=os.path.join(self.temp_dir, "eviction_test.db"), max_entries=3
        )

        # Create 5 test files
        files = []
        for i in range(5):
            f = os.path.join(self.temp_dir, f"test_{i}.sql")
            with open(f, "w") as file:
                file.write(f"SELECT {i};")
            files.append(f)

        # Cache all 5 files
        for i, f in enumerate(files):
            cache.set(f, {"id": i})

        # Check stats
        stats = cache.get_stats()
        self.assertEqual(stats["entry_count"], 3)  # Should have evicted 2

    def test_clear_cache(self):
        """Test clearing all cache entries."""
        # Add some entries
        for i in range(3):
            f = os.path.join(self.temp_dir, f"test_{i}.sql")
            with open(f, "w") as file:
                file.write(f"SELECT {i};")
            self.cache.set(f, {"id": i})

        # Clear cache
        deleted = self.cache.clear()
        self.assertEqual(deleted, 3)

        # Verify cache is empty
        stats = self.cache.get_stats()
        self.assertEqual(stats["entry_count"], 0)

    def test_get_stats(self):
        """Test cache statistics."""
        # Add entry
        self.cache.set(self.test_file, {"test": "data"})

        # Get stats
        stats = self.cache.get_stats()
        self.assertEqual(stats["entry_count"], 1)
        self.assertEqual(stats["max_entries"], 10)
        self.assertGreater(stats["cache_size_mb"], 0)
        self.assertEqual(stats["ttl_days"], 1)


if __name__ == "__main__":
    unittest.main()
