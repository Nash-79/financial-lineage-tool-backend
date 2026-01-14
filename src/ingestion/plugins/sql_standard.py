"""Standard SQL parser plugin using sqlglot."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List

import sqlglot
from sqlglot import exp

from .base import Edge, LineagePlugin, LineageResult, Node

logger = logging.getLogger(__name__)


class StandardSqlPlugin(LineagePlugin):
    """SQL lineage parser plugin based on sqlglot."""

    def __init__(self, default_dialect: str = "auto") -> None:
        self.default_dialect = default_dialect

    @property
    def supported_extensions(self) -> List[str]:
        return [".sql", ".ddl", ".hql"]

    def parse(self, content: str, context: Dict[str, Any]) -> LineageResult:
        dialect = (context.get("dialect") or self.default_dialect or "auto").strip()
        parsed = self._parse_sql(content, dialect)
        result = self._build_lineage_result(parsed)
        result.metadata["parsed"] = parsed
        result.metadata["dialect"] = dialect
        return result

    def _parse_sql(self, sql_content: str, dialect: str) -> Dict[str, Any]:
        try:
            from ..config.sql_dialects import resolve_dialect_for_parsing

            try:
                resolved_dialect = resolve_dialect_for_parsing(dialect)
            except ValueError:
                resolved_dialect = dialect

            expressions = sqlglot.parse(sql_content, read=resolved_dialect)
            if not expressions:
                return self._fallback_regex_parse(sql_content)

            result = {
                "read": set(),
                "write": None,
                "columns": [],
                "functions_and_procedures": set(),
                "views": set(),
                "triggers": [],
                "synonyms": [],
                "materialized_views": set(),
                "procedure_calls": [],
                "writes": set(),
            }

            for ast in expressions:
                if not ast:
                    continue

                write_types = (exp.Insert, exp.Update, exp.Create)
                if hasattr(exp, "CreateTable"):
                    write_types += (exp.CreateTable,)

                if isinstance(ast, write_types):
                    kind = ast.args.get("kind", "").upper()
                    target_name = ast.this.sql()

                    if kind == "VIEW":
                        result["views"].add(target_name)
                        result["writes"].add(target_name)
                    elif kind == "MATERIALIZED VIEW":
                        result["materialized_views"].add(target_name)
                        result["writes"].add(target_name)
                    elif kind == "TRIGGER":
                        trigger_name = target_name
                        target_table = ast.args.get("table")
                        target_table_name = target_table.sql() if target_table else None
                        result["triggers"].append(
                            {"name": trigger_name, "target_table": target_table_name}
                        )
                    elif kind == "SYNONYM":
                        synonym_name = target_name
                        target_obj = ast.expression
                        target_obj_name = target_obj.sql() if target_obj else None
                        result["synonyms"].append(
                            {"name": synonym_name, "target_object": target_obj_name}
                        )
                    elif kind in ("FUNCTION", "PROCEDURE"):
                        result["functions_and_procedures"].add(target_name)
                    elif isinstance(ast.this, exp.Table):
                        result["writes"].add(target_name)

                elif isinstance(ast, exp.Command):
                    cmd_upper = (
                        ast.this.upper()
                        if isinstance(ast.this, str)
                        else str(ast.this).upper()
                    )
                    expression = (
                        ast.expression.sql()
                        if hasattr(ast.expression, "sql")
                        else str(ast.expression)
                    )

                    if cmd_upper == "CREATE":
                        proc_match = re.search(
                            r"(?i)CREATE\s+(?:OR\s+ALTER\s+)?(?:PROCEDURE|PROC)\s+([^\s\(]+)",
                            expression,
                        )
                        if proc_match:
                            result["functions_and_procedures"].add(proc_match.group(1))

                        trigger_match = re.search(
                            r"(?i)TRIGGER\s+([^\s]+)\s+ON\s+([^\s]+)", expression
                        )
                        if trigger_match:
                            result["triggers"].append(
                                {
                                    "name": trigger_match.group(1),
                                    "target_table": trigger_match.group(2),
                                }
                            )

                        synonym_match = re.search(
                            r"(?i)SYNONYM\s+([^\s]+)\s+FOR\s+([^\s]+)", expression
                        )
                        if synonym_match:
                            result["synonyms"].append(
                                {
                                    "name": synonym_match.group(1),
                                    "target_object": synonym_match.group(2),
                                }
                            )

                for table in ast.find_all(exp.Table):
                    tbl_name = table.sql()
                    if tbl_name not in result["writes"]:
                        result["read"].add(tbl_name)

                result["procedure_calls"].extend(self._extract_procedure_calls(ast))

                if hasattr(ast, "expression") and isinstance(
                    ast.expression, exp.Select
                ):
                    select_expression = ast.expression
                    for projection in select_expression.find_all(exp.Alias):
                        target_col = projection.this
                        lineage = projection.expression.lineage()
                        source_cols = {
                            col.sql() for col in lineage.find_all(exp.Column)
                        }
                        result["columns"].append(
                            {
                                "target": target_col.sql(),
                                "sources": list(source_cols),
                                "transformation": projection.expression.sql(
                                    dialect=resolved_dialect
                                ),
                            }
                        )

            if result["writes"]:
                result["write"] = list(result["writes"])[0]
            elif not result["write"] and (result["read"] or result["columns"]):
                result["write"] = "console"

            result["read"] = list(result["read"])
            result["functions_and_procedures"] = list(
                result["functions_and_procedures"]
            )
            result["views"] = list(result["views"])
            result["materialized_views"] = list(result["materialized_views"])
            result["writes"] = list(result["writes"])
            return result

        except Exception as exc:
            logger.warning("SQL parsing failed, using fallback: %s", exc)
            return self._fallback_regex_parse(sql_content)

    def _fallback_regex_parse(self, content: str) -> Dict[str, Any]:
        result = {
            "read": [],
            "write": None,
            "columns": [],
            "functions_and_procedures": [],
            "views": [],
            "triggers": [],
            "synonyms": [],
            "materialized_views": [],
            "procedure_calls": [],
        }

        patterns = {
            "functions_and_procedures": r"(?i)CREATE\s+(?:OR\s+ALTER\s+|OR\s+REPLACE\s+)?(?:PROCEDURE|PROC|FUNCTION)\s+([a-zA-Z0-9_\.]+)",
            "views": r"(?i)CREATE\s+(?:OR\s+ALTER\s+|OR\s+REPLACE\s+)?VIEW\s+([a-zA-Z0-9_\.]+)",
            "tables": r"(?i)CREATE\s+TABLE\s+([a-zA-Z0-9_\.]+)",
        }

        for ptype, pattern in patterns.items():
            matches = re.findall(pattern, content)
            if ptype == "tables":
                if matches:
                    result["write"] = matches[0]
            else:
                result[ptype] = list(set(matches))

        return result

    def _extract_procedure_calls(self, ast: exp.Expression) -> List[Dict[str, Any]]:
        calls = []
        if hasattr(exp, "Command"):
            for command in ast.find_all(exp.Command):
                proc_name = command.this if hasattr(command, "this") else str(command)
                calls.append(
                    {
                        "name": str(proc_name),
                        "type": "stored_procedure",
                        "target_tables": [],
                    }
                )

        for func in ast.find_all(exp.Anonymous):
            func_name = func.this if hasattr(func, "this") else str(func)
            if func_name and func_name.upper() not in (
                "COUNT",
                "SUM",
                "AVG",
                "MIN",
                "MAX",
                "CAST",
                "CONVERT",
            ):
                calls.append(
                    {
                        "name": str(func_name),
                        "type": "function_call",
                        "target_tables": [],
                    }
                )

        return calls

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

        write_target = parsed.get("write")
        views = set(parsed.get("views", []))
        materialized = set(parsed.get("materialized_views", []))

        write_label = None
        if write_target and write_target != "console":
            if write_target in materialized:
                write_label = "MaterializedView"
            elif write_target in views:
                write_label = "View"
            else:
                write_label = "Table"
            add_node(
                Node(
                    name=write_target,
                    label=write_label,
                    type=write_label,
                    properties={"name": write_target},
                )
            )

        for asset_name in parsed.get("read", []):
            if asset_name == write_target:
                continue
            external_refs.append(asset_name)
            add_node(
                Node(
                    name=asset_name,
                    label="DataAsset",
                    type="Table",
                    properties={"name": asset_name, "external_ref": True},
                )
            )

        if write_target and write_label:
            rel_type = (
                "DERIVES"
                if write_target in views or write_target in materialized
                else "READS_FROM"
            )
            for asset_name in parsed.get("read", []):
                if asset_name == write_target:
                    continue
                edges.append(
                    Edge(
                        source=write_target,
                        target=asset_name,
                        relationship=rel_type,
                        properties={
                            "source_label": write_label,
                            "target_label": "DataAsset",
                        },
                    )
                )

        for col_lineage in parsed.get("columns", []):
            target_col_name = col_lineage.get("target")
            if not target_col_name or not write_target:
                continue
            target_key = f"{write_target}.{target_col_name}"
            add_node(
                Node(
                    name=target_key,
                    label="Column",
                    type="Column",
                    properties={"name": target_col_name},
                )
            )
            edges.append(
                Edge(
                    source=write_target,
                    target=target_key,
                    relationship="CONTAINS",
                    properties={
                        "source_label": write_label,
                        "target_label": "Column",
                    },
                )
            )

            logic = col_lineage.get("transformation", "")
            trans_key = hashlib.sha256(
                f"{target_key}:{logic}".encode("utf-8")
            ).hexdigest()
            trans_name = f"transformation:{trans_key}"
            add_node(
                Node(
                    name=trans_name,
                    label="Transformation",
                    type="Transformation",
                    properties={"logic": logic},
                )
            )
            edges.append(
                Edge(
                    source=trans_name,
                    target=target_key,
                    relationship="GENERATES",
                    properties={
                        "source_label": "Transformation",
                        "target_label": "Column",
                    },
                )
            )

            for source_col in col_lineage.get("sources", []):
                parts = source_col.split(".")
                source_table = parts[0] if len(parts) > 1 else "unknown"
                source_col_name = parts[-1]
                source_key = f"{source_table}.{source_col_name}"

                add_node(
                    Node(
                        name=source_key,
                        label="Column",
                        type="Column",
                        properties={"name": source_col_name},
                    )
                )
                add_node(
                    Node(
                        name=source_table,
                        label="DataAsset",
                        type="Table",
                        properties={"name": source_table, "external_ref": True},
                    )
                )
                edges.append(
                    Edge(
                        source=source_table,
                        target=source_key,
                        relationship="CONTAINS",
                        properties={
                            "source_label": "DataAsset",
                            "target_label": "Column",
                        },
                    )
                )
                edges.append(
                    Edge(
                        source=source_key,
                        target=trans_name,
                        relationship="INPUT_TO",
                        properties={
                            "source_label": "Column",
                            "target_label": "Transformation",
                        },
                    )
                )

        for func_name in parsed.get("functions_and_procedures", []):
            add_node(
                Node(
                    name=func_name,
                    label="FunctionOrProcedure",
                    type="FunctionOrProcedure",
                    properties={"name": func_name},
                )
            )

        for trigger in parsed.get("triggers", []):
            trigger_name = trigger.get("name")
            if not trigger_name:
                continue
            add_node(
                Node(
                    name=trigger_name,
                    label="Trigger",
                    type="Trigger",
                    properties={"name": trigger_name},
                )
            )
            target_table = trigger.get("target_table")
            if target_table:
                add_node(
                    Node(
                        name=target_table,
                        label="DataAsset",
                        type="Table",
                        properties={"name": target_table, "external_ref": True},
                    )
                )
                edges.append(
                    Edge(
                        source=trigger_name,
                        target=target_table,
                        relationship="ATTACHED_TO",
                        properties={
                            "source_label": "Trigger",
                            "target_label": "DataAsset",
                        },
                    )
                )

        for synonym in parsed.get("synonyms", []):
            synonym_name = synonym.get("name")
            if not synonym_name:
                continue
            add_node(
                Node(
                    name=synonym_name,
                    label="Synonym",
                    type="Synonym",
                    properties={"name": synonym_name},
                )
            )
            target_obj = synonym.get("target_object")
            if target_obj:
                add_node(
                    Node(
                        name=target_obj,
                        label="DataAsset",
                        type="Table",
                        properties={"name": target_obj, "external_ref": True},
                    )
                )
                edges.append(
                    Edge(
                        source=synonym_name,
                        target=target_obj,
                        relationship="ALIAS_OF",
                        properties={
                            "source_label": "Synonym",
                            "target_label": "DataAsset",
                        },
                    )
                )

        for mv_name in parsed.get("materialized_views", []):
            add_node(
                Node(
                    name=mv_name,
                    label="MaterializedView",
                    type="MaterializedView",
                    properties={"name": mv_name},
                )
            )

        for proc_call in parsed.get("procedure_calls", []):
            proc_name = proc_call.get("name")
            if not proc_name or not write_target:
                continue
            add_node(
                Node(
                    name=proc_name,
                    label="FunctionOrProcedure",
                    type="FunctionOrProcedure",
                    properties={"name": proc_name},
                )
            )
            edges.append(
                Edge(
                    source=write_target,
                    target=proc_name,
                    relationship="CALLS",
                    properties={
                        "source_label": write_label,
                        "target_label": "FunctionOrProcedure",
                    },
                )
            )

        return LineageResult(nodes=nodes, edges=edges, external_refs=external_refs)
