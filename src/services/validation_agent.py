"""
Post-ingestion validation agent for parsing correctness and gap detection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.ingestion.plugins.base import LineageResult, LineagePlugin
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.utils.urn import generate_urn, normalize_asset_path

logger = logging.getLogger(__name__)


@dataclass
class ValidationSummary:
    """Validation summary for a single file."""

    status: str
    expected_nodes: int
    expected_edges: int
    missing_nodes: List[Dict[str, Any]] = field(default_factory=list)
    missing_edges: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable summary."""
        return {
            "status": self.status,
            "expected_nodes": self.expected_nodes,
            "expected_edges": self.expected_edges,
            "missing_nodes": self.missing_nodes,
            "missing_edges": self.missing_edges,
            "missing_nodes_count": len(self.missing_nodes),
            "missing_edges_count": len(self.missing_edges),
            "error": self.error,
        }


class ValidationAgent:
    """Validates parsed lineage results against Neo4j state."""

    def __init__(self, graph_client: Neo4jGraphClient) -> None:
        self.graph_client = graph_client

    def validate_content(
        self,
        *,
        content: str,
        plugin: Optional[LineagePlugin],
        file_path: str,
        project_id: Optional[str] = None,
        dialect: Optional[str] = None,
    ) -> ValidationSummary:
        """Parse content with a plugin and validate against graph state."""
        if not plugin:
            return ValidationSummary(
                status="skipped",
                expected_nodes=0,
                expected_edges=0,
                error="no_plugin",
            )

        try:
            context = {"file_path": file_path}
            if dialect:
                context["dialect"] = dialect
            result = plugin.parse(content, context)
        except Exception as exc:
            logger.warning("Validation parsing failed for %s: %s", file_path, exc)
            return ValidationSummary(
                status="error",
                expected_nodes=0,
                expected_edges=0,
                error=str(exc),
            )

        return self.validate_lineage_result(
            result=result,
            project_id=project_id,
        )

    def validate_lineage_result(
        self,
        *,
        result: LineageResult,
        project_id: Optional[str] = None,
    ) -> ValidationSummary:
        """Validate a LineageResult against graph state."""
        expected_nodes, expected_edges = self._build_expectations(result, project_id)
        node_ids = [node["id"] for node in expected_nodes]
        edge_keys = [
            {
                "source_id": edge["source_id"],
                "target_id": edge["target_id"],
                "relationship_type": edge["relationship_type"],
            }
            for edge in expected_edges
        ]

        existing_nodes = self._fetch_existing_nodes(node_ids)
        existing_edges = self._fetch_existing_edges(edge_keys)

        missing_nodes = [
            node for node in expected_nodes if node["id"] not in existing_nodes
        ]
        missing_edges = [
            edge
            for edge in expected_edges
            if (edge["source_id"], edge["target_id"], edge["relationship_type"])
            not in existing_edges
        ]

        status = "passed"
        if missing_nodes or missing_edges:
            status = "failed"

        return ValidationSummary(
            status=status,
            expected_nodes=len(expected_nodes),
            expected_edges=len(expected_edges),
            missing_nodes=missing_nodes,
            missing_edges=missing_edges,
        )

    def _build_expectations(
        self,
        result: LineageResult,
        project_id: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Build expected nodes and edges based on parser output."""
        node_ids: Dict[Tuple[str, str], str] = {}
        fallback_ids: Dict[str, str] = {}
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        def register_node(
            label: str,
            name: str,
            properties: Optional[Dict[str, Any]] = None,
        ) -> str:
            node_key = (label, name)
            if node_key in node_ids:
                return node_ids[node_key]

            entity_id = self._generate_id(label, name, project_id)
            node_ids[node_key] = entity_id
            fallback_ids.setdefault(name, entity_id)
            nodes.append(
                {
                    "id": entity_id,
                    "label": label,
                    "name": name,
                    "properties": properties or {},
                }
            )
            return entity_id

        for node in result.nodes:
            register_node(node.label, node.name, node.properties)

        for external in result.external_refs:
            register_node(
                "DataAsset",
                external,
                {"external_ref": True, "name": external},
            )

        for edge in result.edges:
            source_label = (
                edge.properties.get("source_label") if edge.properties else None
            )
            target_label = (
                edge.properties.get("target_label") if edge.properties else None
            )

            if source_label:
                source_id = node_ids.get((source_label, edge.source))
            else:
                source_id = fallback_ids.get(edge.source)
            if target_label:
                target_id = node_ids.get((target_label, edge.target))
            else:
                target_id = fallback_ids.get(edge.target)

            if not source_id:
                source_id = register_node(
                    "DataAsset",
                    edge.source,
                    {"external_ref": True, "name": edge.source},
                )
            if not target_id:
                target_id = register_node(
                    "DataAsset",
                    edge.target,
                    {"external_ref": True, "name": edge.target},
                )

            edges.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "relationship_type": edge.relationship,
                    "source_name": edge.source,
                    "target_name": edge.target,
                }
            )

        return nodes, edges

    def _generate_id(self, label: str, name: str, project_id: Optional[str]) -> str:
        resolved_project = project_id or "default"
        normalized = normalize_asset_path(name)
        return generate_urn(label, resolved_project, normalized)

    def _fetch_existing_nodes(self, node_ids: List[str]) -> set[str]:
        if not node_ids:
            return set()

        records = self.graph_client._execute_query(
            """
            MATCH (n)
            WHERE n.id IN $ids
            RETURN n.id as id
            """,
            {"ids": node_ids},
        )
        return {record.get("id") for record in records if record.get("id")}

    def _fetch_existing_edges(
        self,
        edges: List[Dict[str, str]],
    ) -> set[Tuple[str, str, str]]:
        if not edges:
            return set()

        records = self.graph_client._execute_query(
            """
            UNWIND $edges AS edge
            MATCH (source {id: edge.source_id})-[r]->(target {id: edge.target_id})
            WHERE type(r) = edge.relationship_type
            RETURN
                edge.source_id as source_id,
                edge.target_id as target_id,
                edge.relationship_type as relationship_type
            """,
            {"edges": edges},
        )
        return {
            (
                record.get("source_id"),
                record.get("target_id"),
                record.get("relationship_type"),
            )
            for record in records
            if record.get("source_id")
            and record.get("target_id")
            and record.get("relationship_type")
        }
