"""Performance benchmark comparing tree-sitter and AST Python parsers."""

from __future__ import annotations

import os
import time

import pytest

from src.ingestion.plugins.python_ast import PythonAstPlugin
from src.ingestion.plugins.python_treesitter import PythonTreesitterPlugin


def _build_python_sample(lines: int = 200) -> str:
    blocks = []
    for i in range(lines // 4):
        blocks.append(
            "\n".join(
                [
                    f"def fn_{i}(x):",
                    f"    y = x + {i}",
                    "    return y",
                    "",
                ]
            )
        )
    return "\n".join(blocks)


@pytest.mark.performance
def test_treesitter_vs_ast_benchmark():
    if os.getenv("SKIP_PERF_TESTS") == "true":
        pytest.skip("Performance benchmarks skipped by environment")

    content = _build_python_sample()
    treesitter = PythonTreesitterPlugin()
    ast_parser = PythonAstPlugin()

    iterations = 20

    start = time.perf_counter()
    for _ in range(iterations):
        treesitter.parse(content, {"file_path": "benchmark.py"})
    treesitter_duration = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        ast_parser.parse(content, {"file_path": "benchmark.py"})
    ast_duration = time.perf_counter() - start

    assert treesitter_duration > 0
    assert ast_duration > 0
    assert treesitter_duration <= ast_duration * 10
