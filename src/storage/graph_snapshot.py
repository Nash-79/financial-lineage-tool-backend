"""
Neo4j snapshot helper for pre-ingestion exports.

Creates full JSON exports of nodes and edges for audit/comparison.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.storage.artifact_manager import RunContext

logger = logging.getLogger(__name__)


@dataclass
class GraphSnapshotResult:
    """Summary for a graph snapshot export."""

    path: str
    node_count: int
    edge_count: int
    timestamp: str
    project_name: str
    ingestion_id: str
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    file_paths: Optional[List[str]] = None


class GraphSnapshotManager:
    """Create pre-ingestion Neo4j snapshots under /data/{project}/{run}/KG."""

    def __init__(
        self, graph_client: Neo4jGraphClient, storage_root: str = "data"
    ) -> None:
        self.graph_client = graph_client
        self.storage_root = Path(storage_root)

    def create_snapshot(
        self,
        *,
        project_name: str,
        ingestion_id: str,
        project_id: Optional[str] = None,
        run_id: Optional[str] = None,
        run_dir: Optional[Path] = None,
        file_paths: Optional[List[str]] = None,
        phase: str = "pre",
    ) -> GraphSnapshotResult:
        """Export a project/file-scoped graph snapshot to JSON."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        snapshot_path = self._build_snapshot_path(
            project_name=project_name,
            ingestion_id=ingestion_id,
            timestamp=timestamp,
            run_dir=run_dir,
            phase=phase,
        )

        nodes = self._fetch_nodes(project_id=project_id, file_paths=file_paths)
        edges = self._fetch_edges(project_id=project_id, file_paths=file_paths)

        label_counts: Dict[str, int] = {}
        for node in nodes:
            for label in node.get("labels", []) or []:
                label_counts[label] = label_counts.get(label, 0) + 1

        relationship_counts: Dict[str, int] = {}
        for edge in edges:
            rel_type = edge.get("type") or "UNKNOWN"
            relationship_counts[rel_type] = relationship_counts.get(rel_type, 0) + 1

        snapshot_payload = {
            "metadata": {
                "phase": phase,
                "project_name": project_name,
                "project_id": project_id,
                "ingestion_id": ingestion_id,
                "run_id": run_id,
                "file_paths": file_paths or [],
                "timestamp": datetime.utcnow().isoformat(),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "node_label_counts": label_counts,
                "relationship_type_counts": relationship_counts,
            },
            "nodes": nodes,
            "edges": edges,
        }

        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with snapshot_path.open("w", encoding="utf-8") as handle:
                json.dump(
                    snapshot_payload, handle, indent=2, ensure_ascii=False, default=str
                )
        except Exception as exc:
            logger.error("Failed to write graph snapshot: %s", exc)
            raise

        return GraphSnapshotResult(
            path=str(snapshot_path),
            node_count=len(nodes),
            edge_count=len(edges),
            timestamp=timestamp,
            project_name=project_name,
            ingestion_id=ingestion_id,
            project_id=project_id,
            run_id=run_id,
            file_paths=file_paths,
        )

    def _build_snapshot_path(
        self,
        *,
        project_name: str,
        ingestion_id: str,
        timestamp: str,
        run_dir: Optional[Path] = None,
        phase: str = "pre",
    ) -> Path:
        """Resolve the snapshot path under /data/{project}/{run}/KG."""
        if run_dir:
            return (
                Path(run_dir)
                / "KG"
                / f"neo4j_snapshot_{phase}_{timestamp}_{ingestion_id}.json"
            )
        sanitized = RunContext._sanitize_project_name(project_name)
        return (
            self.storage_root
            / sanitized
            / "KG"
            / f"neo4j_snapshot_{phase}_{timestamp}_{ingestion_id}.json"
        )

    def _fetch_nodes(
        self,
        *,
        project_id: Optional[str],
        file_paths: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Fetch project/file-scoped node data from Neo4j."""
        where_clauses = []
        params: Dict[str, Any] = {}
        if project_id:
            where_clauses.append("n.project_id = $project_id")
            params["project_id"] = project_id
        if file_paths:
            where_clauses.append(
                "(n.source_file IN $file_paths OR n.file_path IN $file_paths OR n.path IN $file_paths)"
            )
            params["file_paths"] = file_paths
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        records = self.graph_client._execute_query(
            f"""
            MATCH (n)
            {where_sql}
            RETURN n.id as id, labels(n) as labels, properties(n) as properties
            """,
            params,
        )
        return [
            {
                "id": record.get("id"),
                "labels": record.get("labels") or [],
                "properties": record.get("properties") or {},
            }
            for record in records
        ]

    def _fetch_edges(
        self,
        *,
        project_id: Optional[str],
        file_paths: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Fetch project/file-scoped relationship data from Neo4j."""
        where_clauses = []
        params: Dict[str, Any] = {}
        if project_id:
            where_clauses.append("source.project_id = $project_id")
            where_clauses.append("target.project_id = $project_id")
            params["project_id"] = project_id
        if file_paths:
            where_clauses.append(
                "(source.source_file IN $file_paths OR source.file_path IN $file_paths OR source.path IN $file_paths)"
            )
            where_clauses.append(
                "(target.source_file IN $file_paths OR target.file_path IN $file_paths OR target.path IN $file_paths)"
            )
            params["file_paths"] = file_paths
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        records = self.graph_client._execute_query(
            f"""
            MATCH (source)-[r]->(target)
            {where_sql}
            RETURN
                source.id as source_id,
                target.id as target_id,
                type(r) as type,
                properties(r) as properties
            """,
            params,
        )
        return [
            {
                "source_id": record.get("source_id"),
                "target_id": record.get("target_id"),
                "type": record.get("type"),
                "properties": record.get("properties") or {},
            }
            for record in records
        ]
