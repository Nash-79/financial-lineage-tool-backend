"""
LLM-based Lineage Inference Service

This service uses Ollama to propose "missing" lineage edges by analyzing
code context and existing graph structure. It generates structured edge
proposals with confidence scores and supporting evidence.
"""

from typing import List, Dict, Any, Optional
import logging
import json

logger = logging.getLogger(__name__)


class LineageInferenceService:
    """
    Service for LLM-driven lineage edge inference.

    Uses Ollama to analyze code chunks and graph context to propose
    potential lineage relationships that weren't captured by deterministic parsing.
    """

    def __init__(
        self,
        ollama_client,
        neo4j_client,
        qdrant_client,
        model_name: str = "llama3.1:8b",
    ):
        """
        Initialize the lineage inference service.

        Args:
            ollama_client: Ollama client for LLM calls
            neo4j_client: Neo4j client for graph queries
            qdrant_client: Qdrant client for code chunk retrieval
            model_name: Ollama model to use for inference
        """
        self.ollama = ollama_client
        self.graph = neo4j_client
        self.qdrant = qdrant_client
        self.model_name = model_name

    async def retrieve_context(
        self,
        scope: str,
        max_nodes: int = 20,
        max_chunks: int = 10,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant graph and code context for edge inference.

        Args:
            scope: Scope identifier (e.g., file path, repository name)
            max_nodes: Maximum number of graph nodes to include
            max_chunks: Maximum number of code chunks to include
            project_id: Optional project ID to filter context

        Returns:
            Dictionary containing graph nodes, relationships, and code chunks
        """
        logger.info(f"Retrieving context for scope: {scope}, project_id: {project_id}")

        context = {"nodes": [], "relationships": [], "code_chunks": []}

        try:
            # Retrieve graph nodes with label filters for performance
            # Labels: File, DataAsset, Column, FunctionOrProcedure
            if project_id:
                node_query = """
                MATCH (n)
                WHERE (n:File OR n:DataAsset OR n:Column OR n:FunctionOrProcedure)
                  AND (n.source_file CONTAINS $scope OR n.path CONTAINS $scope)
                  AND n.project_id = $project_id
                RETURN n
                LIMIT $max_nodes
                """
                params = {
                    "scope": scope,
                    "max_nodes": max_nodes,
                    "project_id": project_id,
                }
            else:
                node_query = """
                MATCH (n)
                WHERE (n:File OR n:DataAsset OR n:Column OR n:FunctionOrProcedure)
                  AND (n.source_file CONTAINS $scope OR n.path CONTAINS $scope)
                RETURN n
                LIMIT $max_nodes
                """
                params = {"scope": scope, "max_nodes": max_nodes}

            nodes_result = self.graph._execute_query(node_query, params)

            for record in nodes_result:
                node = record["n"]
                context["nodes"].append(
                    {
                        "id": node.get("id"),
                        "type": list(node.labels)[0] if node.labels else "Unknown",
                        "properties": dict(node),
                    }
                )

            # Retrieve relationships between these nodes
            if context["nodes"]:
                node_ids = [n["id"] for n in context["nodes"]]
                rel_query = """
                MATCH (a)-[r]->(b)
                WHERE a.id IN $node_ids AND b.id IN $node_ids
                RETURN a.id as source, type(r) as type, b.id as target, properties(r) as props
                """

                rels_result = self.graph._execute_query(
                    rel_query, {"node_ids": node_ids}
                )

                for record in rels_result:
                    context["relationships"].append(
                        {
                            "source": record["source"],
                            "target": record["target"],
                            "type": record["type"],
                            "properties": record["props"],
                        }
                    )

            # Retrieve code chunks from Qdrant using semantic search
            try:
                # Generate embedding for the scope using Ollama
                from ..api.config import config

                query_vector = await self.ollama.embed(
                    text=scope, model=config.EMBEDDING_MODEL
                )

                # Search Qdrant for similar code chunks
                if config.ENABLE_HYBRID_SEARCH:
                    search_results = await self.qdrant.hybrid_search(
                        "code_chunks",
                        query_text=scope,
                        dense_vector=query_vector,
                        limit=max_chunks,
                        filter_conditions=None,
                    )
                else:
                    search_results = await self.qdrant.search(
                        collection="code_chunks",
                        vector=query_vector,
                        limit=max_chunks,
                        filter_conditions=None,  # Could add file_path filter if needed
                    )

                for result in search_results:
                    payload = result.get("payload", {})
                    context["code_chunks"].append(
                        {
                            "content": payload.get("content"),
                            "file_path": payload.get("file_path"),
                            "language": payload.get("language"),
                            "tables_referenced": payload.get("tables_referenced", []),
                        }
                    )

                logger.info(
                    f"Retrieved {len(context['code_chunks'])} code chunks from Qdrant"
                )

            except Exception as e:
                # Graceful degradation: continue without code chunks if Qdrant/embedding fails
                logger.warning(f"Qdrant search failed (graceful degradation): {e}")
                logger.info("Continuing with graph-only context")

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")

        return context

    async def propose_edges(
        self, context: Dict[str, Any], edge_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Use LLM to propose potential lineage edges based on context.

        Args:
            context: Context dictionary from retrieve_context()
            edge_types: Optional list of edge types to focus on

        Returns:
            List of edge proposals
        """
        logger.info("Generating edge proposals using LLM")

        if not edge_types:
            edge_types = ["READS_FROM", "WRITES_TO", "CALLS", "DEPENDS_ON"]

        # Build prompt for LLM
        prompt = self._build_inference_prompt(context, edge_types)

        try:
            # Call Ollama to generate JSON response
            response_text = await self.ollama.generate(
                prompt=prompt,
                model=self.model_name,
                temperature=0.1,  # Low temperature for more deterministic output
            )

            # Parse LLM response (expect JSON array)
            proposals = json.loads(response_text)

            # Validate proposals
            validated_proposals = []
            for proposal in proposals:
                if self._validate_proposal(proposal, context):
                    validated_proposals.append(proposal)
                else:
                    logger.warning(f"Invalid proposal filtered out: {proposal}")

            logger.info(f"Generated {len(validated_proposals)} valid proposals")
            return validated_proposals

        except Exception as e:
            logger.error(f"Error generating proposals: {e}")
            return []

    def _validate_proposal(
        self, proposal: Dict[str, Any], context: Dict[str, Any]
    ) -> bool:
        """
        Validate a single edge proposal.

        Args:
            proposal: Proposal to validate
            context: Original context

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["source_id", "target_id", "relationship_type", "confidence"]

        # Check required fields
        for field in required_fields:
            if field not in proposal:
                return False

        # Check confidence range
        if not (0.0 <= proposal["confidence"] <= 1.0):
            return False

        # Check that referenced nodes exist in context
        node_ids = {n["id"] for n in context.get("nodes", [])}
        if (
            proposal["source_id"] not in node_ids
            or proposal["target_id"] not in node_ids
        ):
            return False

        return True

    def _build_inference_prompt(
        self, context: Dict[str, Any], edge_types: List[str]
    ) -> str:
        """
        Build LLM prompt for edge inference.

        Args:
            context: Context dictionary
            edge_types: List of edge types to infer

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are a data lineage analyst. Given the following code and graph context, identify potential data lineage relationships.

Focus on these relationship types: {', '.join(edge_types)}

Graph Context:
{json.dumps(context.get('nodes', []), indent=2)}

Code Context:
{json.dumps(context.get('code_chunks', []), indent=2)}

For each potential relationship you identify, provide:
1. source_id: URN of the source entity (must be from the graph context)
2. target_id: URN of the target entity (must be from the graph context)
3. relationship_type: One of {edge_types}
4. confidence: Float between 0.0 and 1.0
5. evidence: Brief explanation citing specific code or graph patterns

Return your response as a JSON array of relationship objects. Example:
[
  {{
    "source_id": "urn:li:data_asset:project:source_table",
    "target_id": "urn:li:data_asset:project:target_table",
    "relationship_type": "READS_FROM",
    "confidence": 0.85,
    "evidence": "Python file contains SELECT statement from this table"
  }}
]

Return ONLY valid JSON, no markdown formatting or explanation.
"""
        return prompt

    def ingest_proposals(
        self, proposals: List[Dict[str, Any]], default_status: str = "pending_review"
    ) -> int:
        """
        Ingest edge proposals into the Neo4j graph.

        Args:
            proposals: List of edge proposals from propose_edges()
            default_status: Status to assign to inferred edges

        Returns:
            Number of edges successfully ingested
        """
        logger.info(f"Ingesting {len(proposals)} edge proposals")

        ingested_count = 0

        for proposal in proposals:
            try:
                # Add edge with LLM-specific metadata
                self.graph.add_relationship(
                    source_id=proposal["source_id"],
                    target_id=proposal["target_id"],
                    relationship_type=proposal["relationship_type"],
                    source="ollama_llm",
                    confidence=proposal["confidence"],
                    status=default_status,
                    evidence=proposal.get("evidence", ""),
                )
                ingested_count += 1
            except Exception as e:
                logger.error(f"Failed to ingest proposal: {e}")
                continue

        logger.info(
            f"Successfully ingested {ingested_count}/{len(proposals)} proposals"
        )
        return ingested_count
