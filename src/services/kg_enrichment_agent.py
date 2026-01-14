"""
Knowledge graph enrichment agent for post-ingestion LLM edges.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.models.inference import LineageEdgeProposal
from src.services.inference_service import OpenRouterService

logger = logging.getLogger(__name__)

DEFAULT_KG_MODEL = "mistralai/devstral-2512:free"


@dataclass
class KGEnrichmentResult:
    """Summary of KG enrichment run."""

    model: str
    proposed_edges: int
    accepted_edges: int
    skipped_edges: int
    confidence_min: Optional[float] = None
    confidence_avg: Optional[float] = None
    confidence_max: Optional[float] = None
    accepted: List[Dict[str, Any]] = field(default_factory=list)
    skipped: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable summary."""
        return {
            "model": self.model,
            "proposed_edges": self.proposed_edges,
            "accepted_edges": self.accepted_edges,
            "skipped_edges": self.skipped_edges,
            "confidence_min": self.confidence_min,
            "confidence_avg": self.confidence_avg,
            "confidence_max": self.confidence_max,
            "accepted": self.accepted,
            "skipped": self.skipped,
            "error": self.error,
        }


class KGEnrichmentAgent:
    """Proposes and writes LLM edges directly to Neo4j."""

    def __init__(
        self,
        graph_client: Neo4jGraphClient,
        openrouter_service: OpenRouterService,
        model_name: str = DEFAULT_KG_MODEL,
    ) -> None:
        self.graph_client = graph_client
        self.openrouter_service = openrouter_service
        self.model_name = model_name

    async def enrich_file(
        self,
        *,
        code_snippet: str,
        file_path: str,
        project_id: Optional[str],
        ingestion_id: Optional[str] = None,
        max_context_nodes: int = 200,
    ) -> KGEnrichmentResult:
        """Run KG enrichment for a single file."""
        try:
            context_nodes = self._fetch_context_nodes(
                file_path=file_path,
                project_id=project_id,
                limit=max_context_nodes,
            )
            context_ids = {node["id"] for node in context_nodes if node.get("id")}
            if not context_ids:
                return KGEnrichmentResult(
                    model=self.model_name,
                    proposed_edges=0,
                    accepted_edges=0,
                    skipped_edges=0,
                )

            proposals = await self.openrouter_service.predict_lineage(
                code_snippet,
                context_nodes,
                model=self.model_name,
            )

            if not proposals:
                return KGEnrichmentResult(
                    model=self.model_name,
                    proposed_edges=0,
                    accepted_edges=0,
                    skipped_edges=0,
                )

            accepted, skipped = self._filter_proposals(
                proposals=proposals,
                context_ids=context_ids,
            )

            existing_edges = self._fetch_existing_edges(
                [
                    {
                        "source_id": edge.source_node,
                        "target_id": edge.target_node,
                        "relationship_type": self._sanitize_relationship(
                            edge.relationship_type
                        ),
                    }
                    for edge in accepted
                ]
            )

            created = []
            for proposal in accepted:
                rel_type = self._sanitize_relationship(proposal.relationship_type)
                edge_key = (proposal.source_node, proposal.target_node, rel_type)
                if edge_key in existing_edges:
                    skipped.append(
                        {
                            "source": proposal.source_node,
                            "target": proposal.target_node,
                            "relationship_type": rel_type,
                            "reason": "edge_exists",
                        }
                    )
                    continue

                self.graph_client.add_relationship(
                    source_id=proposal.source_node,
                    target_id=proposal.target_node,
                    relationship_type=rel_type,
                    source="llm",
                    model=self.model_name,
                    confidence=proposal.confidence,
                    status="proposed",
                    reasoning=proposal.reasoning,
                    project_id=project_id,
                    source_file=file_path,
                    ingestion_id=ingestion_id,
                )
                created.append(
                    {
                        "source": proposal.source_node,
                        "target": proposal.target_node,
                        "relationship_type": rel_type,
                        "confidence": proposal.confidence,
                        "reasoning": proposal.reasoning,
                    }
                )

            confidences = [edge["confidence"] for edge in created] if created else []
            return KGEnrichmentResult(
                model=self.model_name,
                proposed_edges=len(proposals),
                accepted_edges=len(created),
                skipped_edges=len(skipped),
                confidence_min=min(confidences) if confidences else None,
                confidence_avg=mean(confidences) if confidences else None,
                confidence_max=max(confidences) if confidences else None,
                accepted=created,
                skipped=skipped,
            )
        except Exception as exc:
            logger.warning("KG enrichment failed for %s: %s", file_path, exc)
            return KGEnrichmentResult(
                model=self.model_name,
                proposed_edges=0,
                accepted_edges=0,
                skipped_edges=0,
                error=str(exc),
            )

    def _fetch_context_nodes(
        self,
        *,
        file_path: str,
        project_id: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        where_clause = "n.source_file = $file_path"
        params: Dict[str, Any] = {"file_path": file_path, "limit": limit}
        if project_id:
            where_clause += " AND n.project_id = $project_id"
            params["project_id"] = project_id

        records = self.graph_client._execute_query(
            f"""
            MATCH (n)
            WHERE {where_clause}
            RETURN n.id as id, labels(n) as labels, n.name as name, properties(n) as properties
            LIMIT $limit
            """,
            params,
        )
        nodes: List[Dict[str, Any]] = []
        for record in records:
            labels = record.get("labels") or []
            nodes.append(
                {
                    "id": record.get("id"),
                    "label": labels[0] if labels else "Unknown",
                    "name": record.get("name"),
                    "properties": record.get("properties") or {},
                }
            )
        return nodes

    def _filter_proposals(
        self,
        *,
        proposals: List[LineageEdgeProposal],
        context_ids: set[str],
    ) -> Tuple[List[LineageEdgeProposal], List[Dict[str, Any]]]:
        accepted: List[LineageEdgeProposal] = []
        skipped: List[Dict[str, Any]] = []

        for proposal in proposals:
            if (
                proposal.source_node not in context_ids
                or proposal.target_node not in context_ids
            ):
                skipped.append(
                    {
                        "source": proposal.source_node,
                        "target": proposal.target_node,
                        "relationship_type": proposal.relationship_type,
                        "reason": "missing_context_node",
                    }
                )
                continue
            accepted.append(proposal)

        return accepted, skipped

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

    def _sanitize_relationship(self, relationship_type: str) -> str:
        if not relationship_type:
            return "RELATED_TO"
        sanitized = re.sub(r"[^A-Za-z0-9_]", "_", relationship_type.strip().upper())
        if not sanitized:
            return "RELATED_TO"
        if sanitized[0].isdigit():
            sanitized = f"REL_{sanitized}"
        return sanitized
