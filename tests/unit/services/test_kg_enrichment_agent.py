from typing import Any, Dict, List

import pytest

from src.models.inference import LineageEdgeProposal
from src.services.kg_enrichment_agent import KGEnrichmentAgent


class FakeGraph:
    def __init__(self, nodes: List[Dict[str, Any]]):
        self.nodes = nodes
        self.relationships: List[Dict[str, Any]] = []

    def _execute_query(
        self, query: str, parameters: Dict[str, Any] | None = None
    ) -> List[Dict[str, Any]]:
        parameters = parameters or {}
        if "n.source_file" in query:
            return [
                {
                    "id": node["id"],
                    "labels": [node.get("label", "Node")],
                    "name": node.get("name"),
                    "properties": node.get("properties", {}),
                }
                for node in self.nodes
            ]
        if "UNWIND $edges" in query:
            return []
        return []

    def add_relationship(
        self, source_id: str, target_id: str, relationship_type: str, **properties: Any
    ) -> None:
        self.relationships.append(
            {
                "source_id": source_id,
                "target_id": target_id,
                "relationship_type": relationship_type,
                **properties,
            }
        )


class FakeOpenRouter:
    async def predict_lineage(
        self,
        code_snippet: str,
        context_nodes: List[Any],
        model: str = None,
        prompt_override: str = None,
    ):
        ids = [
            node if isinstance(node, str) else node.get("id") for node in context_nodes
        ]
        return [
            LineageEdgeProposal(
                source_node=ids[0],
                target_node=ids[1],
                relationship_type="reads-from",
                confidence=0.9,
                reasoning="uses data",
            ),
            LineageEdgeProposal(
                source_node="urn:li:missing",
                target_node=ids[1],
                relationship_type="READS",
                confidence=0.5,
                reasoning="missing node",
            ),
        ]


@pytest.mark.asyncio
async def test_kg_enrichment_agent_writes_edges():
    nodes = [
        {"id": "urn:li:table:proj:table_a", "label": "Table", "name": "table_a"},
        {"id": "urn:li:table:proj:table_b", "label": "Table", "name": "table_b"},
    ]
    graph = FakeGraph(nodes)
    agent = KGEnrichmentAgent(graph_client=graph, openrouter_service=FakeOpenRouter())

    result = await agent.enrich_file(
        code_snippet="SELECT * FROM table_a",
        file_path="a.sql",
        project_id="proj",
        ingestion_id="ingest-1",
    )

    assert result.proposed_edges == 2
    assert result.accepted_edges == 1
    assert graph.relationships
    assert graph.relationships[0]["relationship_type"] == "READS_FROM"
