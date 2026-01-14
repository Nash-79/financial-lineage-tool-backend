"""Tree-sitter based Python parser plugin."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from tree_sitter import Parser
from tree_sitter_python import language as python_language

from .base import LineagePlugin, LineageResult, Node
from .python_ast import PythonAstPlugin

logger = logging.getLogger(__name__)


class PythonTreesitterPlugin(LineagePlugin):
    """Python parser plugin using tree-sitter with AST fallback."""

    def __init__(
        self,
        prefer_ast_for_small_files: bool = True,
        ast_max_lines: int = 100,
        sql_extraction_enabled: bool = True,
    ) -> None:
        self.prefer_ast_for_small_files = prefer_ast_for_small_files
        self.ast_max_lines = ast_max_lines
        self.sql_extraction_enabled = sql_extraction_enabled
        self.parser = Parser()
        self.parser.set_language(python_language())
        self.ast_plugin = PythonAstPlugin(sql_extraction_enabled=sql_extraction_enabled)

    @property
    def supported_extensions(self) -> List[str]:
        return [".py", ".pyw"]

    def parse(self, content: str, context: Dict[str, Any]) -> LineageResult:
        line_count = content.count("\n") + 1
        if self.prefer_ast_for_small_files and line_count <= self.ast_max_lines:
            try:
                result = self.ast_plugin.parse(content, context)
                result.metadata["parser"] = "ast"
                return result
            except Exception:
                pass

        content_bytes = content.encode("utf-8", errors="ignore")
        tree = self.parser.parse(content_bytes)
        root = tree.root_node

        classes: List[str] = []
        functions: List[str] = []
        imports: List[str] = []

        def node_text(node) -> str:
            return content_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="ignore"
            )

        def walk(node) -> None:
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    classes.append(node_text(name_node))
            elif node.type in {"function_definition", "async_function_definition"}:
                name_node = node.child_by_field_name("name")
                if name_node:
                    functions.append(node_text(name_node))
            elif node.type == "import_statement":
                import_text = node_text(node)
                imports.extend(self._extract_imports(import_text))
            elif node.type == "import_from_statement":
                import_text = node_text(node)
                imports.extend(self._extract_imports(import_text))

            for child in node.children:
                walk(child)

        walk(root)

        parsed = {
            "classes": [
                {"name": name, "docstring": "", "bases": []} for name in classes
            ],
            "functions": [
                {"name": name, "docstring": "", "args": []} for name in functions
            ],
            "imports": imports,
            "table_references": [],
        }

        if self.sql_extraction_enabled:
            parsed["table_references"] = self._extract_python_table_references(content)

        result = self._build_lineage_result(parsed)
        result.metadata["parser"] = "treesitter"
        result.metadata["has_error"] = root.has_error
        return result

    def _extract_imports(self, import_text: str) -> List[str]:
        imports: List[str] = []
        if import_text.startswith("import "):
            parts = import_text.replace("import ", "").split(",")
            for part in parts:
                name = part.strip().split(" as ")[0].strip()
                if name:
                    imports.append(name)
        elif import_text.startswith("from "):
            match = re.match(r"from\s+([\w.]+)\s+import\s+(.+)", import_text)
            if match:
                module = match.group(1)
                names = match.group(2).split(",")
                for name in names:
                    clean = name.strip().split(" as ")[0].strip()
                    if clean:
                        imports.append(f"{module}.{clean}")
        return imports

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
                    properties={"name": cls["name"]},
                )
            )

        for func in parsed.get("functions", []):
            add_node(
                Node(
                    name=func["name"],
                    label="Function",
                    type="Function",
                    properties={"name": func["name"]},
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
