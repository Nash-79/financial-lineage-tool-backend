"""Parser plugins for lineage extraction."""

from .base import Edge, LineagePlugin, LineageResult, Node
from .json_enricher import JsonEnricherPlugin
from .python_ast import PythonAstPlugin

try:
    from .python_treesitter import PythonTreesitterPlugin
except Exception:  # pragma: no cover - optional dependency
    PythonTreesitterPlugin = None
from .sql_standard import StandardSqlPlugin

__all__ = [
    "Edge",
    "JsonEnricherPlugin",
    "LineagePlugin",
    "LineageResult",
    "Node",
    "PythonAstPlugin",
    "PythonTreesitterPlugin",
    "StandardSqlPlugin",
]
