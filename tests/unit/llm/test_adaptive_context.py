"""Unit tests for AdaptiveContextManager."""

import pytest
from unittest.mock import MagicMock
from src.llm.adaptive_context import AdaptiveContextManager


class TestAdaptiveContextManager:
    """Test suite for AdaptiveContextManager."""

    @pytest.fixture
    def context_manager(self):
        """Create AdaptiveContextManager instance for testing."""
        return AdaptiveContextManager(
            max_tokens=3000,
            question_budget=500,
            response_budget=1000,
        )

    @pytest.fixture
    def mock_nodes(self):
        """Create mock retrieved nodes."""
        nodes = []
        for i in range(10):
            node = MagicMock()
            # Each node has ~200 tokens of text
            node.text = f"This is node {i}. " * 50  # ~200 characters = ~50 tokens
            node.score = 1.0 - (i * 0.1)  # Decreasing relevance scores
            node.metadata = {"file_path": f"file_{i}.sql", "line": i * 10}
            nodes.append(node)
        return nodes

    def test_initialization(self, context_manager):
        """Test AdaptiveContextManager initialization."""
        assert context_manager.max_tokens == 3000
        assert context_manager.question_budget == 500
        assert context_manager.response_budget == 1000
        assert context_manager.context_budget == 1500  # 3000 - 500 - 1000
        assert context_manager.trim_count == 0
        assert context_manager.tokens_removed == 0

    def test_context_budget_calculation(self):
        """Test context budget is correctly calculated."""
        manager = AdaptiveContextManager(
            max_tokens=5000,
            question_budget=800,
            response_budget=1200,
        )
        assert manager.context_budget == 3000  # 5000 - 800 - 1200

    def test_trim_context_no_trimming_needed(self, context_manager, mock_nodes):
        """Test that context is not trimmed when within budget."""
        # Use only 3 nodes (should be ~150 tokens, well within budget)
        small_nodes = mock_nodes[:3]
        question = "What is the schema?"

        trimmed_nodes, info = context_manager.trim_context(small_nodes, question)

        # Should keep all nodes
        assert len(trimmed_nodes) == 3
        assert info["original_nodes"] == 3
        assert info["trimmed_nodes"] == 3
        assert info["nodes_removed"] == 0
        assert info["trim_applied"] is False
        assert info["tokens_used"] <= info["tokens_available"]

    def test_trim_context_with_trimming(self, context_manager):
        """Test that context is trimmed when exceeding budget."""
        # Create nodes with large text to exceed budget
        large_nodes = []
        for i in range(20):
            node = MagicMock()
            # Each node has ~1000 characters = ~250 tokens
            node.text = "A" * 1000
            node.score = 1.0 - (i * 0.05)
            node.metadata = {"file_path": f"large_{i}.sql"}
            large_nodes.append(node)

        question = "Test question"

        trimmed_nodes, info = context_manager.trim_context(large_nodes, question)

        # Should trim some nodes
        assert len(trimmed_nodes) < len(large_nodes)
        assert info["nodes_removed"] > 0
        assert info["trim_applied"] is True
        assert info["tokens_removed"] > 0
        assert context_manager.trim_count == 1
        assert context_manager.tokens_removed > 0

    def test_trim_context_respects_min_nodes(self, context_manager):
        """Test that trimming always keeps minimum number of nodes."""
        # Create 5 nodes that exceed budget individually
        oversized_nodes = []
        for i in range(5):
            node = MagicMock()
            # Each node has 2000 characters = ~500 tokens (exceeds context budget)
            node.text = "X" * 2000
            node.score = 1.0
            node.metadata = {"file_path": f"huge_{i}.sql"}
            oversized_nodes.append(node)

        question = "Test"

        trimmed_nodes, info = context_manager.trim_context(
            oversized_nodes, question, min_nodes=3
        )

        # Should keep at least min_nodes even if they exceed budget
        assert len(trimmed_nodes) >= 3
        assert info["original_nodes"] == 5

    def test_should_use_tree_summarize_default_threshold(self, context_manager):
        """Test tree_summarize recommendation with default threshold."""
        # <= 10 nodes -> False
        assert context_manager.should_use_tree_summarize(5) is False
        assert context_manager.should_use_tree_summarize(10) is False

        # > 10 nodes -> True
        assert context_manager.should_use_tree_summarize(11) is True
        assert context_manager.should_use_tree_summarize(20) is True

    def test_should_use_tree_summarize_custom_threshold(self, context_manager):
        """Test tree_summarize recommendation with custom threshold."""
        # Custom threshold = 5
        assert context_manager.should_use_tree_summarize(4, threshold=5) is False
        assert context_manager.should_use_tree_summarize(5, threshold=5) is False
        assert context_manager.should_use_tree_summarize(6, threshold=5) is True

    def test_get_recommended_response_mode_compact(self, context_manager):
        """Test response mode recommendation for small queries."""
        # Small number of nodes and tokens -> compact
        mode = context_manager.get_recommended_response_mode(
            num_nodes=5,
            estimated_tokens=500,
        )
        assert mode == "compact"

    def test_get_recommended_response_mode_tree_many_nodes(self, context_manager):
        """Test response mode recommendation for large node count."""
        # > 10 nodes -> tree_summarize
        mode = context_manager.get_recommended_response_mode(
            num_nodes=15,
            estimated_tokens=800,
        )
        assert mode == "tree_summarize"

    def test_get_recommended_response_mode_tree_large_context(self, context_manager):
        """Test response mode recommendation for large token count."""
        # Large token count -> tree_summarize
        mode = context_manager.get_recommended_response_mode(
            num_nodes=5,
            estimated_tokens=2000,  # Exceeds context_budget of 1500
        )
        assert mode == "tree_summarize"

    def test_get_node_text_with_text_attribute(self, context_manager):
        """Test extracting text from node with .text attribute."""
        node = MagicMock()
        node.text = "Test content"

        text = context_manager._get_node_text(node)
        assert text == "Test content"

    def test_get_node_text_with_nested_node(self, context_manager):
        """Test extracting text from nested node structure."""
        outer_node = MagicMock()
        inner_node = MagicMock()
        inner_node.text = "Nested content"
        outer_node.node = inner_node
        # Remove text attribute from outer node
        del outer_node.text

        text = context_manager._get_node_text(outer_node)
        assert text == "Nested content"

    def test_get_node_text_with_get_content_method(self, context_manager):
        """Test extracting text from node with get_content() method."""
        node = MagicMock()
        del node.text  # Remove text attribute
        node.get_content.return_value = "Content from method"

        text = context_manager._get_node_text(node)
        assert text == "Content from method"

    def test_estimate_tokens_tiktoken(self, context_manager):
        """Test token estimation with tiktoken."""
        text = "This is a test sentence with multiple words."
        tokens = context_manager._estimate_tokens(text)

        # Should be positive integer
        assert isinstance(tokens, int)
        assert tokens > 0
        # Rough validation: ~1 token per 4 characters
        assert tokens < len(text)

    def test_estimate_tokens_fallback(self, context_manager, monkeypatch):
        """Test token estimation fallback when tiktoken fails."""

        # Mock tiktoken.get_encoding to raise exception
        def mock_get_encoding(encoding_name):
            raise Exception("tiktoken error")

        monkeypatch.setattr("tiktoken.get_encoding", mock_get_encoding)

        text = "A" * 400  # 400 characters
        tokens = context_manager._estimate_tokens(text)

        # Fallback: 1 token = 4 characters
        assert tokens == 100

    def test_get_metrics(self, context_manager):
        """Test metrics retrieval."""
        metrics = context_manager.get_metrics()

        assert metrics["max_tokens"] == 3000
        assert metrics["context_budget"] == 1500
        assert metrics["trim_count"] == 0
        assert metrics["tokens_removed_total"] == 0

    def test_get_metrics_after_trimming(self, context_manager):
        """Test metrics after context trimming."""
        # Create large nodes to trigger trimming
        large_nodes = []
        for i in range(30):
            node = MagicMock()
            node.text = "X" * 1000  # ~250 tokens each
            node.score = 1.0
            node.metadata = {}
            large_nodes.append(node)

        # Trim context twice
        context_manager.trim_context(large_nodes, "Question 1")
        context_manager.trim_context(large_nodes, "Question 2")

        metrics = context_manager.get_metrics()

        assert metrics["trim_count"] == 2
        assert metrics["tokens_removed_total"] > 0

    def test_trim_context_preserves_order(self, context_manager, mock_nodes):
        """Test that trimming preserves node order (most relevant first)."""
        trimmed_nodes, _ = context_manager.trim_context(mock_nodes, "Test")

        # Check that scores are in descending order (most relevant first)
        for i in range(len(trimmed_nodes) - 1):
            assert trimmed_nodes[i].score >= trimmed_nodes[i + 1].score

    def test_trim_context_info_structure(self, context_manager, mock_nodes):
        """Test that trim_info has all required fields."""
        _, info = context_manager.trim_context(mock_nodes, "Test")

        required_fields = [
            "original_nodes",
            "trimmed_nodes",
            "nodes_removed",
            "tokens_used",
            "tokens_available",
            "tokens_removed",
            "trim_applied",
        ]

        for field in required_fields:
            assert field in info

    def test_multiple_trims_accumulate_metrics(self, context_manager):
        """Test that multiple trims accumulate metrics correctly."""
        large_nodes = []
        for i in range(20):
            node = MagicMock()
            node.text = "Y" * 800
            node.score = 1.0
            node.metadata = {}
            large_nodes.append(node)

        # Perform 3 trims
        context_manager.trim_context(large_nodes, "Q1")
        context_manager.trim_context(large_nodes, "Q2")
        context_manager.trim_context(large_nodes, "Q3")

        metrics = context_manager.get_metrics()
        assert metrics["trim_count"] == 3

    def test_empty_nodes_list(self, context_manager):
        """Test handling of empty nodes list."""
        trimmed_nodes, info = context_manager.trim_context([], "Question")

        assert len(trimmed_nodes) == 0
        assert info["original_nodes"] == 0
        assert info["trimmed_nodes"] == 0
        assert info["trim_applied"] is False

    def test_single_node(self, context_manager):
        """Test handling of single node."""
        node = MagicMock()
        node.text = "Single node content"
        node.score = 1.0
        node.metadata = {}

        trimmed_nodes, info = context_manager.trim_context([node], "Question")

        assert len(trimmed_nodes) == 1
        assert info["original_nodes"] == 1
        assert info["trimmed_nodes"] == 1
        assert info["trim_applied"] is False
