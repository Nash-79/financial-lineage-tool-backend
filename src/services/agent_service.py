"""Lineage agent service for natural language queries."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from src.knowledge_graph.neo4j_client import Neo4jGraphClient
    from .ollama_service import OllamaClient
    from .qdrant_service import QdrantLocalClient


class LocalSupervisorAgent:
    """Supervisor agent for data lineage queries.

    Uses local Ollama LLM combined with vector search (Qdrant) and
    graph database (Neo4j) to answer natural language questions about
    data lineage.

    Attributes:
        ollama: Ollama client for LLM operations.
        qdrant: Qdrant client for vector search.
        graph: Neo4j client for graph queries.
    """

    SYSTEM_PROMPT = """You are a Financial Data Lineage Agent. Your role is to answer questions
about data lineage by analyzing the provided context from code searches and graph queries.

When answering lineage questions:
1. Identify the target entity (table, column)
2. Trace the data flow from sources to target
3. Note any transformations applied
4. Be specific about column mappings and data types

Format your response clearly with:
- Summary: Brief answer
- Lineage Path: Source → Transformation → Target
- Transformations: Details of any data changes
- Confidence: How certain you are

If you don't have enough information, say so clearly."""

    def __init__(
        self,
        ollama: OllamaClient,
        qdrant: QdrantLocalClient,
        graph: Neo4jGraphClient,
        llm_model: str,
        embedding_model: str,
    ):
        """Initialize the supervisor agent.

        Args:
            ollama: Ollama client for LLM operations.
            qdrant: Qdrant client for vector search.
            graph: Neo4j graph client.
            llm_model: LLM model name (e.g., "llama3.1:8b").
            embedding_model: Embedding model name (e.g., "nomic-embed-text").
        """
        self.ollama = ollama
        self.qdrant = qdrant
        self.graph = graph
        self.llm_model = llm_model
        self.embedding_model = embedding_model
        self.logger = logging.getLogger(__name__)

    async def _parallel_search(self, question: str) -> Tuple[List[dict], List[dict]]:
        """Execute vector search and graph search in parallel.

        Args:
            question: The user's question.

        Returns:
            Tuple of (code_results, graph_results).
        """

        async def do_vector_search() -> List[dict]:
            """Embed question and search vector DB."""
            try:
                from src.api.config import config

                query_embedding = await self.ollama.embed(
                    question, self.embedding_model
                )
                if config.ENABLE_HYBRID_SEARCH:
                    results = await self.qdrant.hybrid_search(
                        "code_chunks",
                        query_text=question,
                        dense_vector=query_embedding,
                        limit=5,
                    )
                else:
                    results = await self.qdrant.search(
                        collection="code_chunks", vector=query_embedding, limit=5
                    )
                return results
            except Exception as e:
                self.logger.warning("Vector search failed: %s", e)
                return []

        async def do_graph_search() -> List[dict]:
            """Search graph for entities using batch query."""
            try:
                # Extract potential entity names from question
                words = question.replace("_", " ").split()
                search_terms = [w for w in words if len(w) > 3]

                # Also try singular forms for plural words
                for word in list(search_terms):
                    if word.endswith("s") and len(word) > 4:
                        search_terms.append(word[:-1])

                # Use batch query instead of loop
                if search_terms:
                    # Run in executor since Neo4j driver is sync
                    loop = asyncio.get_event_loop()
                    results = await loop.run_in_executor(
                        None, lambda: self.graph.find_by_names(search_terms, limit=10)
                    )
                    return results
                return []
            except Exception as e:
                self.logger.warning("Graph search failed: %s", e)
                return []

        # Execute both searches in parallel
        results = await asyncio.gather(
            do_vector_search(), do_graph_search(), return_exceptions=True
        )

        # Handle any exceptions from gather
        code_results = results[0] if not isinstance(results[0], Exception) else []
        graph_results = results[1] if not isinstance(results[1], Exception) else []

        if isinstance(results[0], Exception):
            self.logger.warning("Vector search exception: %s", results[0])
        if isinstance(results[1], Exception):
            self.logger.warning("Graph search exception: %s", results[1])

        return code_results, graph_results

    def _get_lineage_info(self, graph_results: List[dict]) -> List[dict]:
        """Get upstream/downstream lineage for found entities.

        Args:
            graph_results: List of entities found in graph search.

        Returns:
            List of lineage info dictionaries.
        """
        lineage_info = []
        for entity in graph_results[:2]:  # Limit to first 2 entities
            entity_id = entity.get("id")
            if entity_id:
                try:
                    upstream = self.graph.get_upstream(entity_id, max_depth=5)
                    downstream = self.graph.get_downstream(entity_id, max_depth=5)
                    lineage_info.append(
                        {
                            "entity": entity,
                            "upstream": upstream[:5],
                            "downstream": downstream[:5],
                        }
                    )
                except Exception as e:
                    self.logger.warning(
                        "Failed to get lineage for %s: %s", entity_id, e
                    )
        return lineage_info

    async def query(self, question: str, memory_context: str = "") -> dict:
        """Process a lineage query.

        Combines vector search and graph traversal to answer natural
        language questions about data lineage. Uses parallel execution
        for independent operations to minimize latency.

        Args:
            question: Natural language question about data lineage.
            memory_context: Optional context from chat memory.

        Returns:
            Dictionary with answer, sources, graph entities, and confidence.
        """
        start_time = time.time()

        # Step 1: Execute vector search and graph search in PARALLEL
        code_results, graph_results = await self._parallel_search(question)

        search_time = time.time() - start_time
        self.logger.info("Parallel search completed in %.1fms", search_time * 1000)

        # Step 2: Get lineage for found entities (sequential - depends on graph_results)
        lineage_info = self._get_lineage_info(graph_results)

        # Step 3: Build context for LLM
        context = ""

        if code_results:
            context += "## Relevant Code:\n\n"
            for result in code_results:
                payload = result.get("payload", {})
                context += f"File: {payload.get('file_path', 'unknown')}\n"
                context += f"```sql\n{payload.get('content', '')[:1000]}\n```\n\n"

        if lineage_info:
            context += "## Knowledge Graph Results:\n\n"
            for info in lineage_info:
                entity = info["entity"]
                context += (
                    f"Entity: {entity.get('name')} ({entity.get('entity_type')})\n"
                )
                if info["upstream"]:
                    context += f"Upstream sources: {len(info['upstream'])} found\n"
                if info["downstream"]:
                    context += f"Downstream targets: {len(info['downstream'])} found\n"
                context += "\n"

        # Construct visual graph data BEFORE LLM call (so it's always returned)
        # Initialize with empty structure to ensure it's never None
        graph_data = {"nodes": [], "edges": []}
        try:
            if lineage_info:
                graph_data = self._build_graph_data(lineage_info)
                self.logger.info(
                    "Built graph data: %s nodes, %s edges",
                    len(graph_data.get("nodes", [])),
                    len(graph_data.get("edges", [])),
                )
        except Exception as e:
            self.logger.warning("Failed to build graph data: %s", e)
            # Keep empty graph_data structure

        if not context:
            context = (
                "No relevant code or graph data found. Please ingest some data first."
            )

        # Prepend memory context if available
        if memory_context:
            context = f"{memory_context}\n\n{context}"

        # Step 4: Generate response with Ollama
        prompt = f"""Question: {question}

{context}

Based on the information above, answer the question about data lineage.
If there's no relevant data, explain what information would be needed."""

        try:
            self.logger.debug("Prompt context length: %s", len(context))
            self.logger.info(
                "Sending prompt to %s (Length: %s)", self.llm_model, len(prompt)
            )
            response = await self.ollama.generate(
                prompt=prompt,
                model=self.llm_model,
                system=self.SYSTEM_PROMPT,
                temperature=0.1,
            )
            self.logger.debug("Received response from LLM (Length: %s)", len(response))

            if not response or not response.strip():
                response = "The LLM returned an empty response. This might be due to memory constraints or model issues. Please check the backend logs."

        except Exception as e:
            self.logger.error("LLM generation failed: %s", e)
            if "500" in str(e):
                response = "Error: The model failed to generate a response (500). This is often due to insufficient memory (OOM) or context window limits. Try restarting Ollama or using a smaller context."
            else:
                response = f"Error generating response: {e}"

        return {
            "question": question,
            "answer": response,
            "sources": [
                r.get("payload", {}).get("file_path")
                for r in code_results
                if r.get("payload")
            ],
            "graph_entities": [e.get("name") for e in graph_results],
            "graph_data": graph_data,
            "confidence": 0.8 if (code_results or graph_results) else 0.3,
        }

    def _build_graph_data(self, lineage_info: list) -> dict:
        """Construct nodes and edges for visual graph."""
        nodes = {}
        edges = []

        for info in lineage_info:
            # Main Entity (Center)
            entity = info["entity"]
            eid = entity.get("id")
            if eid and eid not in nodes:
                nodes[eid] = {
                    "id": eid,
                    "data": {
                        "label": entity.get("name", "Unknown"),
                        "type": entity.get("entity_type", "Node"),
                    },
                    "position": {"x": 0, "y": 0},  # Layout will be handled by frontend
                }

            # Upstream
            for rel in info.get("upstream", []):
                # source -> entity
                sid = rel.get("source")
                if sid and sid not in nodes:
                    source_data = rel.get("source_data", {})
                    nodes[sid] = {
                        "id": sid,
                        "data": {
                            "label": source_data.get("name", sid),
                            "type": source_data.get("entity_type", "Source"),
                        },
                        "position": {"x": 0, "y": 0},
                    }

                if sid and eid:
                    edge_id = f"{sid}-{eid}"
                    edges.append(
                        {
                            "id": edge_id,
                            "source": sid,
                            "target": eid,
                            "label": rel.get("relationship", "RELATED"),
                        }
                    )

            # Downstream
            for rel in info.get("downstream", []):
                # entity -> target
                tid = rel.get("target")
                if tid and tid not in nodes:
                    target_data = rel.get("target_data", {})
                    nodes[tid] = {
                        "id": tid,
                        "data": {
                            "label": target_data.get("name", tid),
                            "type": target_data.get("entity_type", "Target"),
                        },
                        "position": {"x": 0, "y": 0},
                    }

                if eid and tid:
                    edge_id = f"{eid}-{tid}"
                    edges.append(
                        {
                            "id": edge_id,
                            "source": eid,
                            "target": tid,
                            "label": rel.get("relationship", "RELATED"),
                        }
                    )

        # Deduplicate edges based on ID
        unique_edges = {e["id"]: e for e in edges}.values()

        return {"nodes": list(nodes.values()), "edges": list(unique_edges)}
