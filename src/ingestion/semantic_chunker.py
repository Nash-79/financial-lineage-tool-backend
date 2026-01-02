"""
Semantic Chunker for Code Files.

This module implements AST-aware chunking that preserves semantic boundaries
in code files (SQL, Python, configs) for optimal embedding quality.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import sqlglot
from sqlglot import exp
import tiktoken


class ChunkType(Enum):
    """Types of code chunks."""

    SQL_CTE = "sql_cte"
    SQL_STATEMENT = "sql_statement"
    SQL_SUBQUERY = "sql_subquery"
    PYTHON_FUNCTION = "python_function"
    PYTHON_CLASS = "python_class"
    PYTHON_IMPORT_BLOCK = "python_import_block"
    PYTHON_MODULE = "python_module"
    CONFIG_OBJECT = "config_object"
    GENERIC = "generic"


@dataclass
class CodeChunk:
    """Represents a semantic chunk of code."""

    content: str
    chunk_type: ChunkType
    file_path: str
    start_line: int
    end_line: int
    language: str

    # Metadata for lineage
    tables_referenced: list[str] = field(default_factory=list)
    columns_referenced: list[str] = field(default_factory=list)
    functions_defined: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)

    # For embedding
    context_prefix: str = ""  # Parent context (e.g., CTE dependencies)
    token_count: int = 0

    def to_embedding_text(self) -> str:
        """Generate text optimized for embedding."""
        parts = []
        if self.context_prefix:
            parts.append(f"-- Context:\n{self.context_prefix}\n")
        parts.append(f"-- File: {self.file_path}")
        parts.append(f"-- Type: {self.chunk_type.value}")
        if self.tables_referenced:
            parts.append(f"-- Tables: {', '.join(self.tables_referenced)}")
        parts.append(self.content)
        return "\n".join(parts)


class BaseChunker(ABC):
    """Base class for language-specific chunkers."""

    def __init__(self, max_tokens: int = 1500, overlap_tokens: int = 100):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    @abstractmethod
    def chunk(self, content: str, file_path: str) -> list[CodeChunk]:
        """Chunk the content into semantic units."""
        pass


class SQLChunker(BaseChunker):
    """
    SQL-aware chunker that preserves semantic boundaries.

    Chunking strategy:
    1. Parse SQL into AST using sqlglot
    2. Identify CTEs, subqueries, and statements
    3. Keep related CTEs together when under token limit
    4. Include CTE dependencies as context prefix
    """

    def __init__(self, max_tokens: int = 1500, dialect: str = "tsql"):
        super().__init__(max_tokens)
        self.dialect = dialect

    def chunk(self, content: str, file_path: str) -> list[CodeChunk]:
        """Chunk SQL content preserving semantic boundaries."""
        chunks = []

        # Try to parse with sqlglot
        try:
            statements = sqlglot.parse(content, dialect=self.dialect)
        except Exception:
            # Fallback to statement-level splitting
            return self._fallback_chunk(content, file_path)

        for stmt in statements:
            if stmt is None:
                continue

            # Check for CTEs
            ctes = list(stmt.find_all(exp.CTE))

            if ctes:
                chunks.extend(self._chunk_with_ctes(stmt, ctes, file_path))
            else:
                chunks.extend(self._chunk_statement(stmt, file_path))

        return chunks

    def _chunk_with_ctes(
        self, statement: exp.Expression, ctes: list[exp.CTE], file_path: str
    ) -> list[CodeChunk]:
        """Handle statements with CTEs."""
        chunks = []
        cte_map = {}  # CTE name -> CTE sql
        cte_deps = {}  # CTE name -> dependent CTE names

        # Build CTE dependency graph
        for cte in ctes:
            cte_name = cte.alias
            cte_sql = cte.sql(dialect=self.dialect)
            cte_map[cte_name] = cte_sql

            # Find table references within CTE to identify dependencies
            deps = []
            for table in cte.find_all(exp.Table):
                table_name = table.name
                if table_name in cte_map:
                    deps.append(table_name)
            cte_deps[cte_name] = deps

        # Try to keep all CTEs together if under token limit
        full_sql = statement.sql(dialect=self.dialect)
        if self.count_tokens(full_sql) <= self.max_tokens:
            chunk = self._create_chunk(
                content=full_sql,
                chunk_type=ChunkType.SQL_STATEMENT,
                file_path=file_path,
                statement=statement,
            )
            chunks.append(chunk)
        else:
            # Split into individual CTEs with their dependencies as context
            for cte_name, cte_sql in cte_map.items():
                # Build context from dependencies
                context_parts = []
                for dep in cte_deps.get(cte_name, []):
                    if dep in cte_map:
                        context_parts.append(f"-- Depends on CTE: {dep}")
                        context_parts.append(cte_map[dep][:500] + "...")  # Truncated

                chunk = CodeChunk(
                    content=cte_sql,
                    chunk_type=ChunkType.SQL_CTE,
                    file_path=file_path,
                    start_line=0,  # Would need source mapping
                    end_line=0,
                    language="sql",
                    context_prefix="\n".join(context_parts) if context_parts else "",
                    tables_referenced=self._extract_tables(cte_sql),
                    columns_referenced=self._extract_columns(cte_sql),
                    token_count=self.count_tokens(cte_sql),
                )
                chunks.append(chunk)

            # Add the main SELECT (without CTEs) as final chunk
            main_select = statement.find(exp.Select)
            if main_select:
                main_sql = main_select.sql(dialect=self.dialect)
                chunk = self._create_chunk(
                    content=main_sql,
                    chunk_type=ChunkType.SQL_STATEMENT,
                    file_path=file_path,
                    statement=main_select,
                )
                chunk.context_prefix = f"-- CTEs defined: {', '.join(cte_map.keys())}"
                chunks.append(chunk)

        return chunks

    def _chunk_statement(
        self, statement: exp.Expression, file_path: str
    ) -> list[CodeChunk]:
        """Chunk a statement without CTEs."""
        sql = statement.sql(dialect=self.dialect)

        if self.count_tokens(sql) <= self.max_tokens:
            return [
                self._create_chunk(sql, ChunkType.SQL_STATEMENT, file_path, statement)
            ]

        # For large statements, try to split on subqueries
        chunks = []
        subqueries = list(statement.find_all(exp.Subquery))

        if subqueries:
            for sq in subqueries:
                sq_sql = sq.sql(dialect=self.dialect)
                if self.count_tokens(sq_sql) <= self.max_tokens:
                    chunks.append(
                        self._create_chunk(
                            sq_sql, ChunkType.SQL_SUBQUERY, file_path, sq
                        )
                    )

        # If no subqueries or all too large, fall back to text splitting
        if not chunks:
            return self._fallback_chunk(sql, file_path)

        return chunks

    def _create_chunk(
        self,
        content: str,
        chunk_type: ChunkType,
        file_path: str,
        expression: Optional[exp.Expression] = None,
    ) -> CodeChunk:
        """Create a CodeChunk with extracted metadata."""
        return CodeChunk(
            content=content,
            chunk_type=chunk_type,
            file_path=file_path,
            start_line=0,
            end_line=0,
            language="sql",
            tables_referenced=self._extract_tables(content),
            columns_referenced=self._extract_columns(content),
            token_count=self.count_tokens(content),
        )

    def _extract_tables(self, sql: str) -> list[str]:
        """Extract table names from SQL."""
        tables = []
        try:
            parsed = sqlglot.parse_one(sql, dialect=self.dialect)
            for table in parsed.find_all(exp.Table):
                full_name = ".".join(
                    filter(None, [table.catalog, table.db, table.name])
                )
                tables.append(full_name)
        except Exception:
            # Fallback regex
            pattern = r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z_][\w.]*)"
            tables = re.findall(pattern, sql, re.IGNORECASE)
        return list(set(tables))

    def _extract_columns(self, sql: str) -> list[str]:
        """Extract column references from SQL."""
        columns = []
        try:
            parsed = sqlglot.parse_one(sql, dialect=self.dialect)
            for col in parsed.find_all(exp.Column):
                full_name = ".".join(filter(None, [col.table, col.name]))
                columns.append(full_name)
        except Exception:
            pass
        return list(set(columns))

    def _fallback_chunk(self, content: str, file_path: str) -> list[CodeChunk]:
        """Fallback chunking by SQL statement boundaries."""
        chunks = []

        # Split on semicolons while handling string literals
        statements = sqlglot.parse(content, dialect=self.dialect)

        current_chunk = ""
        current_tokens = 0

        for stmt in statements:
            if stmt is None:
                continue
            stmt_sql = stmt.sql(dialect=self.dialect)
            stmt_tokens = self.count_tokens(stmt_sql)

            if current_tokens + stmt_tokens > self.max_tokens and current_chunk:
                chunks.append(
                    CodeChunk(
                        content=current_chunk,
                        chunk_type=ChunkType.SQL_STATEMENT,
                        file_path=file_path,
                        start_line=0,
                        end_line=0,
                        language="sql",
                        tables_referenced=self._extract_tables(current_chunk),
                        columns_referenced=self._extract_columns(current_chunk),
                        token_count=current_tokens,
                    )
                )
                current_chunk = stmt_sql
                current_tokens = stmt_tokens
            else:
                current_chunk += "\n\n" + stmt_sql if current_chunk else stmt_sql
                current_tokens += stmt_tokens

        if current_chunk:
            chunks.append(
                CodeChunk(
                    content=current_chunk,
                    chunk_type=ChunkType.SQL_STATEMENT,
                    file_path=file_path,
                    start_line=0,
                    end_line=0,
                    language="sql",
                    tables_referenced=self._extract_tables(current_chunk),
                    columns_referenced=self._extract_columns(current_chunk),
                    token_count=current_tokens,
                )
            )

        return chunks


class PythonChunker(BaseChunker):
    """
    Python-aware chunker using AST parsing.

    Chunking strategy:
    1. Parse Python AST
    2. Extract functions, classes, and import blocks
    3. Include docstrings and decorators with their targets
    4. Preserve module-level context
    """

    def chunk(self, content: str, file_path: str) -> list[CodeChunk]:
        """Chunk Python content preserving semantic boundaries."""
        import ast

        chunks = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._fallback_chunk(content, file_path)

        lines = content.split("\n")

        # Extract imports as one chunk
        import_lines = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_lines.extend(range(node.lineno - 1, node.end_lineno))

        if import_lines:
            import_lines = sorted(set(import_lines))
            import_content = "\n".join(lines[i] for i in import_lines)
            chunks.append(
                CodeChunk(
                    content=import_content,
                    chunk_type=ChunkType.PYTHON_IMPORT_BLOCK,
                    file_path=file_path,
                    start_line=min(import_lines) + 1,
                    end_line=max(import_lines) + 1,
                    language="python",
                    dependencies=self._extract_imports(import_content),
                    token_count=self.count_tokens(import_content),
                )
            )

        # Process top-level functions and classes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                chunks.append(self._process_function(node, lines, file_path))
            elif isinstance(node, ast.AsyncFunctionDef):
                chunks.append(self._process_function(node, lines, file_path))
            elif isinstance(node, ast.ClassDef):
                chunks.extend(self._process_class(node, lines, file_path))

        return [c for c in chunks if c is not None]

    def _process_function(self, node, lines: list[str], file_path: str) -> CodeChunk:
        """Process a function definition."""
        start = node.lineno - 1
        end = node.end_lineno

        # Include decorators
        if node.decorator_list:
            start = min(d.lineno - 1 for d in node.decorator_list)

        content = "\n".join(lines[start:end])

        return CodeChunk(
            content=content,
            chunk_type=ChunkType.PYTHON_FUNCTION,
            file_path=file_path,
            start_line=start + 1,
            end_line=end,
            language="python",
            functions_defined=[node.name],
            tables_referenced=self._extract_table_refs(content),
            token_count=self.count_tokens(content),
        )

    def _process_class(self, node, lines: list[str], file_path: str) -> list[CodeChunk]:
        """Process a class definition."""
        chunks = []

        start = node.lineno - 1
        end = node.end_lineno

        # Include decorators
        if node.decorator_list:
            start = min(d.lineno - 1 for d in node.decorator_list)

        full_content = "\n".join(lines[start:end])

        # If class is small enough, keep it as one chunk
        if self.count_tokens(full_content) <= self.max_tokens:
            chunks.append(
                CodeChunk(
                    content=full_content,
                    chunk_type=ChunkType.PYTHON_CLASS,
                    file_path=file_path,
                    start_line=start + 1,
                    end_line=end,
                    language="python",
                    functions_defined=[node.name],
                    token_count=self.count_tokens(full_content),
                )
            )
        else:
            # Split class into methods
            class_header = f"class {node.name}:"
            if node.bases:
                bases = ", ".join(self._get_name(b) for b in node.bases)
                class_header = f"class {node.name}({bases}):"

            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_start = child.lineno - 1
                    method_end = child.end_lineno
                    method_content = "\n".join(lines[method_start:method_end])

                    chunks.append(
                        CodeChunk(
                            content=f"# From {class_header}\n{method_content}",
                            chunk_type=ChunkType.PYTHON_FUNCTION,
                            file_path=file_path,
                            start_line=method_start + 1,
                            end_line=method_end,
                            language="python",
                            functions_defined=[f"{node.name}.{child.name}"],
                            context_prefix=class_header,
                            token_count=self.count_tokens(method_content),
                        )
                    )

        return chunks

    def _get_name(self, node) -> str:
        """Get name from AST node."""
        if hasattr(node, "id"):
            return node.id
        if hasattr(node, "attr"):
            return node.attr
        return str(node)

    def _extract_imports(self, content: str) -> list[str]:
        """Extract imported module names."""
        imports = []
        for line in content.split("\n"):
            if line.strip().startswith("import "):
                parts = line.replace("import ", "").split(",")
                imports.extend(p.strip().split(" as ")[0] for p in parts)
            elif line.strip().startswith("from "):
                match = re.match(r"from\s+([\w.]+)", line)
                if match:
                    imports.append(match.group(1))
        return imports

    def _extract_table_refs(self, content: str) -> list[str]:
        """Extract potential table references from Python code."""
        tables = []
        # Look for common patterns like spark.table("...") or df.read_table("...")
        patterns = [
            r'\.table\(["\']([^"\']+)["\']\)',
            r'\.read_table\(["\']([^"\']+)["\']\)',
            r'spark\.sql\(["\'].*?FROM\s+([a-zA-Z_][\w.]*)',
        ]
        for pattern in patterns:
            tables.extend(re.findall(pattern, content, re.IGNORECASE))
        return list(set(tables))

    def _fallback_chunk(self, content: str, file_path: str) -> list[CodeChunk]:
        """Fallback to line-based chunking."""
        lines = content.split("\n")
        chunks = []
        current_lines = []
        current_tokens = 0

        for i, line in enumerate(lines):
            line_tokens = self.count_tokens(line)

            if current_tokens + line_tokens > self.max_tokens and current_lines:
                chunk_content = "\n".join(current_lines)
                chunks.append(
                    CodeChunk(
                        content=chunk_content,
                        chunk_type=ChunkType.GENERIC,
                        file_path=file_path,
                        start_line=i - len(current_lines) + 1,
                        end_line=i,
                        language="python",
                        token_count=current_tokens,
                    )
                )
                # Overlap
                overlap_lines = current_lines[-5:] if len(current_lines) > 5 else []
                current_lines = overlap_lines + [line]
                current_tokens = sum(self.count_tokens(l) for l in current_lines)
            else:
                current_lines.append(line)
                current_tokens += line_tokens

        if current_lines:
            chunk_content = "\n".join(current_lines)
            chunks.append(
                CodeChunk(
                    content=chunk_content,
                    chunk_type=ChunkType.GENERIC,
                    file_path=file_path,
                    start_line=len(lines) - len(current_lines) + 1,
                    end_line=len(lines),
                    language="python",
                    token_count=current_tokens,
                )
            )

        return chunks


class SemanticChunker:
    """
    Main chunker that delegates to language-specific chunkers.
    """

    def __init__(self):
        self.chunkers = {
            "sql": SQLChunker(max_tokens=1500),
            "python": PythonChunker(max_tokens=1000),
        }

    def chunk_file(self, content: str, file_path: str) -> list[CodeChunk]:
        """Chunk a file based on its extension."""
        ext = file_path.lower().split(".")[-1]

        language_map = {
            "sql": "sql",
            "ddl": "sql",
            "dml": "sql",
            "py": "python",
            "pyspark": "python",
        }

        language = language_map.get(ext, "generic")
        chunker = self.chunkers.get(language)

        if chunker:
            return chunker.chunk(content, file_path)
        else:
            # Generic chunking for unsupported languages
            return self._generic_chunk(content, file_path, language)

    def _generic_chunk(
        self, content: str, file_path: str, language: str
    ) -> list[CodeChunk]:
        """Generic token-based chunking."""
        tokenizer = tiktoken.get_encoding("cl100k_base")
        max_tokens = 1000

        chunks = []
        lines = content.split("\n")
        current_lines = []
        current_tokens = 0

        for line in lines:
            line_tokens = len(tokenizer.encode(line))

            if current_tokens + line_tokens > max_tokens and current_lines:
                chunks.append(
                    CodeChunk(
                        content="\n".join(current_lines),
                        chunk_type=ChunkType.GENERIC,
                        file_path=file_path,
                        start_line=0,
                        end_line=0,
                        language=language,
                        token_count=current_tokens,
                    )
                )
                current_lines = [line]
                current_tokens = line_tokens
            else:
                current_lines.append(line)
                current_tokens += line_tokens

        if current_lines:
            chunks.append(
                CodeChunk(
                    content="\n".join(current_lines),
                    chunk_type=ChunkType.GENERIC,
                    file_path=file_path,
                    start_line=0,
                    end_line=0,
                    language=language,
                    token_count=current_tokens,
                )
            )

        return chunks
