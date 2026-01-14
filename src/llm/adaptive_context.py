"""Adaptive context management for preventing Ollama OOM errors.

Dynamically adjusts RAG context size based on:
- Token budget estimation
- Query complexity
- Relevance scores from retrieval
"""

from __future__ import annotations

import logging
from typing import Any

import tiktoken

logger = logging.getLogger(__name__)


class AdaptiveContextManager:
    """Manages context window size to prevent OOM errors.

    Features:
    - Token budget enforcement (max 3000 tokens for local inference)
    - Context trimming by relevance score
    - Automatic tree_summarize for large retrievals (top_k > 10)
    - Logging of context adjustments

    Example:
        >>> manager = AdaptiveContextManager(max_tokens=3000)
        >>> adjusted = manager.trim_context(nodes, question)
        >>> if manager.should_use_tree_summarize(len(nodes)):
        >>>     response_mode = "tree_summarize"
    """

    def __init__(
        self,
        max_tokens: int = 3000,
        question_budget: int = 500,
        response_budget: int = 1000,
    ):
        """Initialize adaptive context manager.

        Args:
            max_tokens: Maximum total tokens allowed (default 3000 for local)
            question_budget: Reserved tokens for question (default 500)
            response_budget: Reserved tokens for response (default 1000)
        """
        self.max_tokens = max_tokens
        self.question_budget = question_budget
        self.response_budget = response_budget

        # Context budget = total - question - response
        self.context_budget = max_tokens - question_budget - response_budget

        # Metrics
        self.trim_count = 0
        self.tokens_removed = 0

        logger.info(
            f"AdaptiveContextManager initialized (max_tokens: {max_tokens}, "
            f"context_budget: {self.context_budget})"
        )

    def trim_context(
        self,
        nodes: list[Any],
        question: str,
        min_nodes: int = 3,
    ) -> tuple[list[Any], dict[str, Any]]:
        """Trim context to fit within token budget.

        Args:
            nodes: Retrieved nodes from vector search (ordered by relevance)
            question: User question
            min_nodes: Minimum number of nodes to keep (default 3)

        Returns:
            Tuple of (trimmed_nodes, adjustment_info)
        """
        # Estimate question tokens
        question_tokens = self._estimate_tokens(question)

        # Calculate available budget for context
        available_budget = self.context_budget

        # Track token usage
        current_tokens = 0
        trimmed_nodes = []

        for i, node in enumerate(nodes):
            # Get node text
            node_text = self._get_node_text(node)
            node_tokens = self._estimate_tokens(node_text)

            # Check if adding this node exceeds budget
            if current_tokens + node_tokens > available_budget:
                # Always keep minimum nodes (top-k most relevant)
                if i < min_nodes:
                    trimmed_nodes.append(node)
                    current_tokens += node_tokens
                    logger.warning(
                        f"Node {i} exceeds budget but kept (min_nodes={min_nodes}). "
                        f"Budget: {available_budget}, Used: {current_tokens + node_tokens}"
                    )
                else:
                    # Trim this and remaining nodes
                    logger.info(
                        f"Trimming context: kept {len(trimmed_nodes)}/{len(nodes)} nodes "
                        f"(tokens: {current_tokens}/{available_budget})"
                    )
                    break
            else:
                trimmed_nodes.append(node)
                current_tokens += node_tokens

        # Calculate adjustment metrics
        nodes_removed = len(nodes) - len(trimmed_nodes)
        tokens_removed = sum(
            self._estimate_tokens(self._get_node_text(n))
            for n in nodes[len(trimmed_nodes) :]
        )

        if nodes_removed > 0:
            self.trim_count += 1
            self.tokens_removed += tokens_removed

        adjustment_info = {
            "original_nodes": len(nodes),
            "trimmed_nodes": len(trimmed_nodes),
            "nodes_removed": nodes_removed,
            "tokens_used": current_tokens,
            "tokens_available": available_budget,
            "tokens_removed": tokens_removed,
            "trim_applied": nodes_removed > 0,
        }

        return trimmed_nodes, adjustment_info

    def should_use_tree_summarize(self, num_nodes: int, threshold: int = 10) -> bool:
        """Determine if tree_summarize should be used instead of compact mode.

        Tree summarize is better for large retrievals (>10 nodes) as it:
        - Reduces memory usage by processing chunks hierarchically
        - Avoids single large prompt with all context
        - Scales better with large top_k values

        Args:
            num_nodes: Number of retrieved nodes
            threshold: Threshold for switching to tree_summarize (default 10)

        Returns:
            True if tree_summarize recommended
        """
        return num_nodes > threshold

    def get_recommended_response_mode(
        self,
        num_nodes: int,
        estimated_tokens: int,
    ) -> str:
        """Get recommended response synthesis mode.

        Args:
            num_nodes: Number of retrieved nodes
            estimated_tokens: Estimated total tokens for context

        Returns:
            Response mode: "compact", "tree_summarize", or "simple_summarize"
        """
        # Large retrievals (>10 nodes) -> tree_summarize
        if num_nodes > 10:
            logger.info(f"Using tree_summarize for large retrieval ({num_nodes} nodes)")
            return "tree_summarize"

        # Large token count -> tree_summarize
        if estimated_tokens > self.context_budget:
            logger.info(
                f"Using tree_summarize for large context "
                f"({estimated_tokens} > {self.context_budget} tokens)"
            )
            return "tree_summarize"

        # Default to compact mode for small/medium queries
        return "compact"

    def _get_node_text(self, node: Any) -> str:
        """Extract text content from a node.

        Args:
            node: LlamaIndex node object

        Returns:
            Text content
        """
        if hasattr(node, "text"):
            return node.text
        elif hasattr(node, "node") and hasattr(node.node, "text"):
            return node.node.text
        elif hasattr(node, "get_content"):
            return node.get_content()
        else:
            return str(node)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Fallback to rough estimate (1 token ~= 4 characters)
            return len(text) // 4

    def get_metrics(self) -> dict[str, Any]:
        """Get context management metrics.

        Returns:
            Dictionary of metrics
        """
        return {
            "max_tokens": self.max_tokens,
            "context_budget": self.context_budget,
            "trim_count": self.trim_count,
            "tokens_removed_total": self.tokens_removed,
        }
