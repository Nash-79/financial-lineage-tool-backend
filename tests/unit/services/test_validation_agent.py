from typing import Any, Dict, List

from src.ingestion.plugins.base import Edge, LineageResult, Node
from src.services.validation_agent import ValidationAgent
from src.utils.urn import generate_urn


class FakeGraph:
    def __init__(
        self, existing_nodes: List[str], existing_edges: List[tuple[str, str, str]]
    ):
        self.existing_nodes = set(existing_nodes)
        self.existing_edges = set(existing_edges)

    def _execute_query(
        self, query: str, parameters: Dict[str, Any] | None = None
    ) -> List[Dict[str, Any]]:
        parameters = parameters or {}
        if "n.id IN" in query:
            ids = parameters.get("ids", [])
            return [
                {"id": node_id} for node_id in ids if node_id in self.existing_nodes
            ]
        if "UNWIND $edges" in query:
            edges = parameters.get("edges", [])
            results = []
            for edge in edges:
                key = (edge["source_id"], edge["target_id"], edge["relationship_type"])
                if key in self.existing_edges:
                    results.append(
                        {
                            "source_id": edge["source_id"],
                            "target_id": edge["target_id"],
                            "relationship_type": edge["relationship_type"],
                        }
                    )
            return results
        return []


def test_validation_agent_passes_when_graph_matches():
    project_id = "proj"
    node_a = generate_urn("Table", project_id, "table_a")
    node_b = generate_urn("Table", project_id, "table_b")
    edge_key = (node_a, node_b, "READS")

    graph = FakeGraph([node_a, node_b], [edge_key])
    agent = ValidationAgent(graph)

    result = LineageResult(
        nodes=[
            Node(name="table_a", label="Table", type="Table"),
            Node(name="table_b", label="Table", type="Table"),
        ],
        edges=[
            Edge(source="table_a", target="table_b", relationship="READS"),
        ],
    )

    summary = agent.validate_lineage_result(result=result, project_id=project_id)
    assert summary.status == "passed"
    assert summary.missing_nodes == []
    assert summary.missing_edges == []


def test_validation_agent_detects_missing_edges():
    project_id = "proj"
    node_a = generate_urn("Table", project_id, "table_a")
    node_b = generate_urn("Table", project_id, "table_b")

    graph = FakeGraph([node_a, node_b], [])
    agent = ValidationAgent(graph)

    result = LineageResult(
        nodes=[
            Node(name="table_a", label="Table", type="Table"),
            Node(name="table_b", label="Table", type="Table"),
        ],
        edges=[
            Edge(source="table_a", target="table_b", relationship="READS"),
        ],
    )

    summary = agent.validate_lineage_result(result=result, project_id=project_id)
    assert summary.status == "failed"
    assert summary.missing_edges
