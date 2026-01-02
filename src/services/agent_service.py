"""Lineage agent service for natural language queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

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

    async def query(self, question: str) -> dict:
        """Process a lineage query.

        Combines vector search and graph traversal to answer natural
        language questions about data lineage.

        Args:
            question: Natural language question about data lineage.

        Returns:
            Dictionary with answer, sources, graph entities, and confidence.
        """

        # Step 1: Search for relevant code in vector DB
        try:
            query_embedding = await self.ollama.embed(question, self.embedding_model)
            code_results = await self.qdrant.search(
                collection="code_chunks", vector=query_embedding, limit=5
            )
        except Exception as e:
            code_results = []
            print(f"Vector search failed: {e}")

        # Step 2: Search graph for entities mentioned in question
        graph_results = []
        # Extract potential entity names (simple approach)
        words = question.replace("_", " ").split()
        for word in words:
            if len(word) > 3:  # Skip short words
                matches = self.graph.find_by_name(word)
                graph_results.extend(matches[:3])

        # Get lineage for found entities
        lineage_info = []
        for entity in graph_results[:2]:
            entity_id = entity.get("id")
            if entity_id:
                upstream = self.graph.get_upstream(entity_id, max_depth=5)
                downstream = self.graph.get_downstream(entity_id, max_depth=5)
                lineage_info.append(
                    {
                        "entity": entity,
                        "upstream": upstream[:5],
                        "downstream": downstream[:5],
                    }
                )

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

        if not context:
            context = (
                "No relevant code or graph data found. Please ingest some data first."
            )

        # Step 4: Generate response with Ollama
        prompt = f"""Question: {question}

{context}

Based on the information above, answer the question about data lineage.
If there's no relevant data, explain what information would be needed."""

        try:
            response = await self.ollama.generate(
                prompt=prompt,
                model=self.llm_model,
                system=self.SYSTEM_PROMPT,
                temperature=0.1,
            )
        except Exception as e:
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
            "confidence": 0.8 if (code_results or graph_results) else 0.3,
        }
