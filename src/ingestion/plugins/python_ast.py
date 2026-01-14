"""Legacy Python AST parser plugin."""

from __future__ import annotations

import ast
import logging
import re
from typing import Any, Dict, List

from .base import LineagePlugin, LineageResult, Node

logger = logging.getLogger(__name__)


class PythonAstPlugin(LineagePlugin):
    """Legacy AST-based Python parser plugin."""

    def __init__(self, sql_extraction_enabled: bool = True) -> None:
        self.sql_extraction_enabled = sql_extraction_enabled

    @property
    def supported_extensions(self) -> List[str]:
        return [".py", ".pyw"]

    def parse(self, content: str, context: Dict[str, Any]) -> LineageResult:
        parsed = self._parse_python(content)
        result = self._build_lineage_result(parsed)
        result.metadata["parsed"] = parsed
        return result

    def _parse_python(self, python_content: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(python_content)
            result = {
                "classes": [],
                "functions": [],
                "imports": [],
                "table_references": [],
                "docstring": ast.get_docstring(tree),
            }

            if self.sql_extraction_enabled:
                result["table_references"] = self._extract_python_table_references(
                    python_content
                )

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    result["classes"].append(
                        {
                            "name": node.name,
                            "docstring": ast.get_docstring(node),
                            "bases": [
                                b.id for b in node.bases if isinstance(b, ast.Name)
                            ],
                        }
                    )
                elif isinstance(node, ast.FunctionDef):
                    result["functions"].append(
                        {
                            "name": node.name,
                            "docstring": ast.get_docstring(node),
                            "args": [arg.arg for arg in node.args.args],
                        }
                    )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        result["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        result["imports"].append(f"{module}.{alias.name}")

            return result
        except Exception as exc:
            logger.warning("Python AST parsing failed: %s", exc)
            return {
                "classes": [],
                "functions": [],
                "imports": [],
                "table_references": [],
                "docstring": "",
            }

    def _extract_python_table_references(self, python_content: str) -> List[str]:
        tables = set()

        from_pattern = r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)"
        tables.update(re.findall(from_pattern, python_content, re.IGNORECASE))

        insert_pattern = r"INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_\.]*)"
        tables.update(re.findall(insert_pattern, python_content, re.IGNORECASE))

        update_pattern = r"UPDATE\s+([a-zA-Z_][a-zA-Z0-9_\.]*)"
        tables.update(re.findall(update_pattern, python_content, re.IGNORECASE))

        return list(tables)

    def _build_lineage_result(self, parsed: Dict[str, Any]) -> LineageResult:
        nodes: List[Node] = []
        edges: List[Edge] = []
        external_refs: List[str] = []
        node_keys = set()

        def add_node(node: Node) -> None:
            key = f"{node.label}:{node.name}"
            if key in node_keys:
                return
            node_keys.add(key)
            nodes.append(node)

        for cls in parsed.get("classes", []):
            add_node(
                Node(
                    name=cls["name"],
                    label="Class",
                    type="Class",
                    properties={
                        "name": cls["name"],
                        "docstring": cls.get("docstring") or "",
                        "bases": cls.get("bases", []),
                    },
                )
            )

        for func in parsed.get("functions", []):
            add_node(
                Node(
                    name=func["name"],
                    label="Function",
                    type="Function",
                    properties={
                        "name": func["name"],
                        "docstring": func.get("docstring") or "",
                        "args": func.get("args", []),
                    },
                )
            )

        for imp in parsed.get("imports", []):
            add_node(
                Node(
                    name=imp,
                    label="Module",
                    type="Module",
                    properties={"name": imp},
                )
            )

        for table in parsed.get("table_references", []):
            external_refs.append(table)
            add_node(
                Node(
                    name=table,
                    label="DataAsset",
                    type="Table",
                    properties={"name": table, "external_ref": True},
                )
            )

        return LineageResult(nodes=nodes, edges=edges, external_refs=external_refs)
