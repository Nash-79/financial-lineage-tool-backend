"""Chat service for OpenRouter-backed evidence-driven responses."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from src.api.config import config
from src.llm.free_tier import DEFAULT_FREE_TIER_MODEL, enforce_free_tier
from src.storage.duckdb_client import get_duckdb_client
from src.utils import metrics
from src.utils.urn import generate_urn, is_valid_urn

BASE_SYSTEM_PROMPT = (
    "You are the Financial Lineage Tool assistant. Your job is to answer questions "
    "about data lineage, dependencies, transformations, and repository artifacts "
    "using ONLY the evidence provided in the request context (vector snippets, graph "
    "results, and metadata). Do not invent tables, columns, files, edges, or SQL logic.\n\n"
    "Rules:\n"
    "- Treat Neo4j/graph evidence as authoritative for lineage claims (upstream/downstream, "
    "DERIVES/READS_FROM, dependency edges).\n"
    "- Treat vector snippets as supporting evidence (code or docs excerpts). If evidence is "
    "missing or ambiguous, say so and propose what to search next.\n"
    "- Prefer precise, testable statements (file path, object name, query/view name, edge/path, "
    "confidence if provided).\n"
    "- Never mention internal implementation details (no \"I used Qdrant/Neo4j\" unless asked). "
    "Just cite evidence identifiers passed in.\n"
    "- Never output hidden reasoning. Provide final conclusions only.\n\n"
    "Output format:\n"
    "Return a single JSON object with:\n"
    "{\n"
    "  \"answer\": string,\n"
    "  \"evidence\": [\n"
    "    { \"type\": \"graph|chunk|doc\", \"id\": string, \"note\": string }\n"
    "  ],\n"
    "  \"next_actions\": [string],\n"
    "  \"warnings\": [string]\n"
    "}\n\n"
    "If the user asks for code changes, respond with steps and minimal patches, "
    "grounded in evidence.\n"
)

ENDPOINT_PROMPTS: Dict[str, str] = {
    "deep": (
        "Additional rules for DEEP:\n"
        "- Synthesize across graph evidence + multiple snippets. If they conflict, call it out "
        "and pick the most authoritative source.\n"
        "- When explaining lineage, include: (a) the key path(s), (b) the transformation boundary "
        "(view/job/model), and (c) what to verify next.\n"
        "- Keep the answer structured in paragraphs or bullets inside the \"answer\" string, "
        "but still emit valid JSON.\n"
    ),
    "graph": (
        "Additional rules for GRAPH:\n"
        "- Answer using graph evidence first. If no graph evidence supports a lineage claim, do not claim it.\n"
        "- Summarize nodes, edges, and paths clearly (entity names + relationship type). Avoid long prose.\n"
    ),
    "semantic": (
        "Additional rules for SEMANTIC:\n"
        "- Focus on the most relevant snippets and return a short summary.\n"
        "- If the user asks lineage questions and no graph evidence is present, explicitly recommend "
        "calling /api/chat/deep or /api/chat/graph in next_actions.\n"
        "- Keep \"answer\" under ~1200 characters unless the user explicitly asked for detail.\n"
    ),
    "text": (
        "Additional rules for TEXT:\n"
        "- You have no retrieval context. Do not pretend you saw the repo or graph.\n"
        "- Provide general guidance, and put specific \"what I would need\" items into next_actions.\n"
    ),
    "title": (
        "Additional rules for TITLE:\n"
        "- Produce a short title (3-7 words) that describes the user's main intent. Output JSON with:\n"
        "{ \"answer\": \"<title>\", \"evidence\": [], \"next_actions\": [], \"warnings\": [] }\n"
    ),
}

LINEAGE_KEYWORDS = {
    "lineage",
    "upstream",
    "downstream",
    "depends",
    "dependency",
    "derive",
    "derived",
    "reads",
    "writes",
    "impact",
    "flows",
}


@dataclass
class ModelAttempt:
    model: str
    error: str
    timestamp: str


class AllModelsFailed(Exception):
    def __init__(self, endpoint: str, attempts: List[ModelAttempt], retry_after: int):
        super().__init__("All free-tier models exhausted")
        self.endpoint = endpoint
        self.attempts = attempts
        self.retry_after = retry_after


class ChatService:
    """Chat service with OpenRouter fallback and evidence mapping."""

    def __init__(
        self,
        *,
        ollama: Any,
        qdrant: Any,
        graph: Any,
        openrouter_api_key: str,
    ) -> None:
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required for ChatService")
        self.ollama = ollama
        self.qdrant = qdrant
        self.graph = graph
        self.api_key = openrouter_api_key
        self.client = httpx.AsyncClient(timeout=120.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def generate(
        self,
        *,
        endpoint: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        memory_context: str = "",
    ) -> Dict[str, Any]:
        endpoint_key = endpoint.lower()
        start_time = time.monotonic()
        metrics.counter(
            "chat_request_count",
            "Chat requests",
            {"endpoint": endpoint_key},
        ).inc()
        project_id, repository_id, project_filter = self._extract_context_ids(context)

        try:
            retrieval = await self._build_retrieval_context(
                endpoint=endpoint_key,
                query=query,
                project_id=project_id,
                project_filter=project_filter,
                repository_id=repository_id,
                memory_context=memory_context,
            )

            # Extract graph data for frontend if available
            graph_data = None
            if endpoint_key in {"deep", "graph"} and self.graph:
                graph_entities = retrieval.get("debug_graph_entities", [])
                graph_relationships = retrieval.get("debug_graph_relationships", [])
                
                if graph_entities or graph_relationships:
                    nodes = []
                    for entity in graph_entities:
                        # Ensure we have a valid ID and label
                        node_id = entity.get("id")
                        label = entity.get("entity_type", "Node")
                        name = entity.get("name", node_id)
                        if node_id:
                            nodes.append({
                                "id": node_id,
                                "label": label,
                                "name": name,
                                "properties": entity
                            })
                            
                    edges = []
                    for rel in graph_relationships:
                        # Ensure source/target exist and are strings
                        source = rel.get("source")
                        target = rel.get("target")
                        rel_type = rel.get("relationship", "RELATED")
                        
                        if source and target:
                            edges.append({
                                "id": f"{source}-{rel_type}-{target}",
                                "source": source,
                                "target": target,
                                "label": rel_type,
                                "properties": rel
                            })
                            
                    if nodes:
                        graph_data = {"nodes": nodes, "edges": edges}
            user_prompt = self._build_user_prompt(query, retrieval["context_text"])
            system_prompt = BASE_SYSTEM_PROMPT + ENDPOINT_PROMPTS.get(endpoint_key, "")

            temperature = self._temperature_for_endpoint(endpoint_key)
            timeout = self._timeout_for_endpoint(endpoint_key)
            models = self._models_for_endpoint(endpoint_key)

            parsed, model_used, parse_failed, attempts, raw_response = await self._call_with_fallback(
                endpoint=endpoint_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                timeout=timeout,
                models=models,
            )
        except Exception as exc:
            metrics.counter(
                "chat_request_failure_count",
                "Chat requests failed",
                {"endpoint": endpoint_key, "error": exc.__class__.__name__},
            ).inc()
            raise
        finally:
            elapsed = time.monotonic() - start_time
            metrics.histogram(
                "chat_latency_seconds",
                "Chat request latency in seconds",
                labels={"endpoint": endpoint_key},
            ).observe(elapsed)

        sources = self._resolve_sources(
            parsed.get("evidence", []), retrieval["evidence"]
        )
        warnings = list(retrieval["warnings"])
        warnings.extend(parsed.get("warnings", []))
        next_actions = list(parsed.get("next_actions", []))

        if endpoint_key == "semantic" and not self._has_graph_sources(sources):
            if self._contains_lineage_keywords(query):
                suggestion = "Consider /api/chat/deep or /api/chat/graph for lineage-aware answers."
                if suggestion not in next_actions:
                    next_actions.append(suggestion)

        if parse_failed and "LLM returned malformed response." not in warnings:
            warnings.append("LLM returned malformed response. Falling back to safe response.")

        primary_model = enforce_free_tier(models[0])[0] if models else DEFAULT_FREE_TIER_MODEL
        if attempts:
            if model_used != primary_model:
                failure_reasons = "; ".join(
                    f"{attempt.model}: {attempt.error}" for attempt in attempts
                )
                warnings.append(
                    f"Model fallback used. Primary '{primary_model}' failed: {failure_reasons}"
                )
            else:
                failure_reasons = "; ".join(
                    f"{attempt.model}: {attempt.error}" for attempt in attempts
                )
                warnings.append(f"Model retries occurred: {failure_reasons}")

        metrics.counter(
            "chat_request_success_count",
            "Chat requests succeeded",
            {"endpoint": endpoint_key},
        ).inc()

        formatted_answer = self._format_answer(
            endpoint=endpoint_key,
            answer_text=parsed.get("answer", "Unable to generate answer"),
            sources=sources,
            warnings=warnings,
            next_actions=next_actions,
            parse_failed=parse_failed,
            raw_candidate=raw_response,
        )

        self._log_chat_event(
            endpoint=endpoint_key,
            query=query,
            project_id=project_id,
            model=model_used,
            attempts=attempts,
            warnings=warnings,
            next_actions=next_actions,
            latency_seconds=elapsed,
        )

        # Persist graph data if associated with a message
        session_id = context.get("session_id") if context else None
        message_id = context.get("message_id") if context else None
        
        if graph_data and session_id and message_id:
            try:
                # Run storage in background to not block response
                db = get_duckdb_client()
                await db.save_chat_artifact(
                    session_id=session_id,
                    message_id=message_id,
                    artifact_type="graph",
                    content=graph_data
                )
            except Exception as e:
                logger.error(f"Failed to persist chat graph artifact: {e}")

        return {
            "response": formatted_answer,
            "sources": sources,
            "next_actions": next_actions,
            "warnings": warnings,
            "model": model_used,
            "graph_data": graph_data,
            "raw_candidate": raw_response if parse_failed else None,
        }

    async def _build_retrieval_context(
        self,
        *,
        endpoint: str,
        query: str,
        project_id: str,
        project_filter: Optional[str],
        repository_id: Optional[str],
        memory_context: str,
    ) -> Dict[str, Any]:
        evidence: List[Dict[str, Any]] = []
        warnings: List[str] = []
        context_blocks: List[str] = []

        if memory_context:
            context_blocks.append("## Memory Context\n" + memory_context.strip())

        vector_limit = self._vector_limit_for_endpoint(endpoint)
        graph_hops = self._graph_hops_for_endpoint(endpoint)
        include_graph = endpoint in {"deep", "graph"}
        include_vectors = endpoint in {"deep", "graph", "semantic"}

        vector_results: List[dict] = []
        if include_vectors and self.ollama and self.qdrant:
            vector_results, vector_warnings = await self._fetch_vector_results(
                query=query,
                project_id=project_filter,
                repository_id=repository_id,
                limit=vector_limit,
            )
            warnings.extend(vector_warnings)
        elif include_vectors:
            warnings.append("Vector search unavailable (missing Ollama or Qdrant).")

        graph_entities: List[dict] = []
        graph_relationships: List[dict] = []
        if include_graph and self.graph:
            try:
                graph_entities, graph_relationships = await self._fetch_graph_context(
                    query=query,
                    project_id=project_filter,
                    max_hops=graph_hops,
                )
            except Exception as exc:
                warnings.append(f"Graph lookup failed: {exc}")
        elif include_graph:
            warnings.append("Graph lookup unavailable (Neo4j not initialized).")

        vector_evidence, vector_blocks = self._format_vector_evidence(
            vector_results, project_id
        )
        vector_block = self._render_vector_block(vector_blocks)
        graph_evidence, graph_block = self._format_graph_evidence(
            graph_entities, graph_relationships, project_id
        )

        evidence.extend(vector_evidence)
        evidence.extend(graph_evidence)

        if endpoint == "deep":
            base_blocks = list(context_blocks)
            if graph_block:
                base_blocks.append(graph_block)
            context_text, kept_blocks, dropped = self._truncate_context(
                base_blocks=[block for block in base_blocks if block],
                vector_blocks=vector_blocks,
            )
            vector_evidence = vector_evidence[: len(kept_blocks)]
            evidence = vector_evidence + graph_evidence
            if dropped > 0:
                warnings.append(
                    f"Context truncated: {dropped} chunks omitted due to token limit"
                )
        else:
            if endpoint == "graph":
                if graph_block:
                    context_blocks.append(graph_block)
                if vector_block:
                    context_blocks.append(vector_block)
            else:
                if vector_block:
                    context_blocks.append(vector_block)
                if graph_block:
                    context_blocks.append(graph_block)
            context_text = "\n\n".join(block for block in context_blocks if block)

        return {
            "context_text": (context_text or "").strip(),
            "evidence": evidence,
            "context_text": (context_text or "").strip(),
            "evidence": evidence,
            "warnings": warnings,
            "debug_graph_entities": graph_entities,
            "debug_graph_relationships": graph_relationships,
        }

    async def _fetch_vector_results(
        self,
        *,
        query: str,
        project_id: Optional[str],
        repository_id: Optional[str],
        limit: int,
    ) -> Tuple[List[dict], List[str]]:
        warnings: List[str] = []
        filter_conditions = self._build_qdrant_filter(project_id, repository_id)

        try:
            embedding = await self.ollama.embed(query, config.EMBEDDING_MODEL)
            if config.ENABLE_HYBRID_SEARCH:
                results = await self.qdrant.hybrid_search(
                    config.QDRANT_COLLECTION,
                    query_text=query,
                    dense_vector=embedding,
                    limit=limit,
                    filter_conditions=filter_conditions,
                )
            else:
                results = await self.qdrant.search(
                    config.QDRANT_COLLECTION,
                    embedding,
                    limit=limit,
                    filter_conditions=filter_conditions,
                )
            return results, warnings
        except Exception as exc:
            warnings.append(f"Vector search failed: {exc}")
            return [], warnings

    async def _fetch_graph_context(
        self,
        *,
        query: str,
        project_id: Optional[str],
        max_hops: int,
    ) -> Tuple[List[dict], List[dict]]:
        terms = self._extract_entity_terms(query)
        if not terms:
            return [], []

        loop = asyncio.get_running_loop()
        entities = await loop.run_in_executor(
            None,
            lambda: self.graph.find_by_names(
                terms, project_id=project_id, limit=10
            ),
        )

        relationships: List[dict] = []
        for entity in entities[:3]:
            entity_id = entity.get("id")
            if not entity_id:
                continue
            upstream = await loop.run_in_executor(
                None,
                lambda: self.graph.get_upstream(
                    entity_id, max_depth=max_hops, project_id=project_id
                ),
            )
            downstream = await loop.run_in_executor(
                None,
                lambda: self.graph.get_downstream(
                    entity_id, max_depth=max_hops, project_id=project_id
                ),
            )
            relationships.extend(upstream or [])
            relationships.extend(downstream or [])

        return entities, relationships

    def _format_vector_evidence(
        self, results: List[dict], project_id: str
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        evidence: List[Dict[str, Any]] = []
        blocks: List[str] = []

        for result in results:
            payload = result.get("payload", {}) or {}
            point_id = result.get("id")
            chunk_text = payload.get("content") or payload.get("text") or ""
            file_path = payload.get("file_path") or payload.get("relative_path") or "unknown"
            chunk_type = payload.get("chunk_type") or payload.get("language") or "unknown"

            chunk_project = payload.get("project_id") or project_id
            evidence_id = generate_urn(
                "qdrant-chunk",
                chunk_project,
                f"{config.QDRANT_COLLECTION}/{point_id}",
            )
            blocks.append(
                "\n".join(
                    [
                        f"[{evidence_id}]",
                        f"File: {file_path}",
                        f"Type: {chunk_type}",
                        f"Content: {chunk_text[:1000]}",
                    ]
                )
            )

            evidence.append(
                {
                    "type": "chunk",
                    "id": evidence_id,
                    "note": f"Vector match from {file_path}",
                    "metadata": {
                        "file_path": file_path,
                        "chunk_type": chunk_type,
                        "score": result.get("score"),
                    },
                }
            )

        return evidence, blocks

    def _format_graph_evidence(
        self,
        entities: List[dict],
        relationships: List[dict],
        project_id: str,
    ) -> Tuple[List[Dict[str, Any]], str]:
        evidence: List[Dict[str, Any]] = []
        lines: List[str] = []
        if entities or relationships:
            lines.append("## Graph Evidence")

        for entity in entities:
            label = entity.get("entity_type") or "Node"
            name = entity.get("name") or entity.get("id") or "unknown"
            node_project = entity.get("project_id") or project_id
            node_urn = generate_urn("neo4j-node", node_project, f"{label}/{name}")
            lines.append(f"[{node_urn}]")
            lines.append(f"Node: {name} ({label})")
            lines.append("")
            evidence.append(
                {
                    "type": "graph",
                    "id": node_urn,
                    "note": f"Graph node {name}",
                    "metadata": {"label": label, "name": name},
                }
            )

        for rel in relationships:
            rel_type = rel.get("relationship") or rel.get("type") or "RELATED"
            source_data = rel.get("source_data", {}) or {}
            target_data = rel.get("target_data", {}) or {}
            source_name = source_data.get("name") or rel.get("source") or "unknown"
            target_name = target_data.get("name") or rel.get("target") or "unknown"
            source_label = source_data.get("entity_type") or "Node"
            target_label = target_data.get("entity_type") or "Node"
            edge_path = f"{rel_type}/{source_label}:{source_name}->{target_label}:{target_name}"
            edge_project = (
                source_data.get("project_id")
                or target_data.get("project_id")
                or project_id
            )
            edge_urn = generate_urn("neo4j-edge", edge_project, edge_path)
            lines.append(f"[{edge_urn}]")
            lines.append(
                f"Path: {source_name} ({source_label}) -> {rel_type} -> {target_name} ({target_label})"
            )
            lines.append("")
            evidence.append(
                {
                    "type": "graph",
                    "id": edge_urn,
                    "note": f"{rel_type} from {source_name} to {target_name}",
                    "metadata": {
                        "relationship": rel_type,
                        "source": source_name,
                        "target": target_name,
                    },
                }
            )

        return evidence, "\n".join(lines).strip()

    def _render_vector_block(self, blocks: List[str]) -> str:
        if not blocks:
            return ""
        return "## Vector Evidence\n" + "\n\n".join(blocks)

    def _truncate_context(
        self, *, base_blocks: List[str], vector_blocks: List[str]
    ) -> Tuple[str, List[str], int]:
        if not vector_blocks:
            context_text = "\n\n".join(base_blocks)
            return context_text, [], 0

        base_text = "\n\n".join(base_blocks).strip()
        kept_blocks = list(vector_blocks)

        def total_tokens(blocks: List[str]) -> int:
            vector_text = self._render_vector_block(blocks)
            combined = "\n\n".join(
                part for part in [base_text, vector_text] if part
            ).strip()
            return len(combined) // 4

        while kept_blocks and total_tokens(kept_blocks) > config.CHAT_CONTEXT_TOKEN_LIMIT:
            kept_blocks.pop()

        dropped = len(vector_blocks) - len(kept_blocks)
        vector_text = self._render_vector_block(kept_blocks)
        context_text = "\n\n".join(
            part for part in [base_text, vector_text] if part
        ).strip()
        return context_text, kept_blocks, dropped

    def _build_user_prompt(self, query: str, context_text: str) -> str:
        if context_text:
            return f"{context_text}\n\n## User Query\n{query}"
        return f"## User Query\n{query}"

    def _models_for_endpoint(self, endpoint: str) -> List[str]:
        mapping = config.get_chat_endpoint_models()
        entry = mapping.get(f"/api/chat/{endpoint}")
        if not entry:
            return [DEFAULT_FREE_TIER_MODEL]
        models = [entry["primary"], entry["secondary"], entry["tertiary"]]
        return models[: max(1, config.CHAT_MAX_RETRIES)]

    def _temperature_for_endpoint(self, endpoint: str) -> float:
        return config.get_chat_endpoint_temperatures().get(endpoint, 0.2)

    def _timeout_for_endpoint(self, endpoint: str) -> float:
        return config.get_chat_endpoint_timeouts().get(endpoint, 30.0)

    def _vector_limit_for_endpoint(self, endpoint: str) -> int:
        if endpoint == "deep":
            return config.CHAT_DEEP_TOP_K
        if endpoint == "semantic":
            return config.CHAT_SEMANTIC_TOP_K
        if endpoint == "graph":
            return config.CHAT_GRAPH_TOP_K
        return 0

    def _graph_hops_for_endpoint(self, endpoint: str) -> int:
        if endpoint == "deep":
            return config.CHAT_DEEP_GRAPH_HOPS
        if endpoint == "graph":
            return config.CHAT_GRAPH_MAX_HOPS
        return 0

    async def _call_with_fallback(
        self,
        *,
        endpoint: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: float,
        models: List[str],
    ) -> Tuple[Dict[str, Any], str, bool, List[ModelAttempt], str]:
        attempts: List[ModelAttempt] = []
        parse_failures = 0
        last_model = models[0] if models else DEFAULT_FREE_TIER_MODEL
        raw_response = ""

        for idx, model in enumerate(models):
            selected_model, downgraded = enforce_free_tier(model)
            last_model = selected_model
            next_model = None
            if idx + 1 < len(models):
                next_model = enforce_free_tier(models[idx + 1])[0]
            if downgraded:
                logger.warning(
                    "Downgrading model '%s' to free-tier model '%s'",
                    model,
                    DEFAULT_FREE_TIER_MODEL,
                )

            try:
                response_text = await self._call_openrouter(
                    model=selected_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    timeout=timeout,
                    enforce_json=(selected_model in config.CHAT_JSON_MODELS),
                )
                raw_response = response_text
            except httpx.TimeoutException:
                attempts.append(
                    ModelAttempt(
                        model=selected_model,
                        error=f"Timeout after {timeout}s",
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )
                if next_model:
                    self._increment_fallback_metric(
                        endpoint, selected_model, next_model, "timeout"
                    )
                metrics.counter(
                    "chat_timeout_count",
                    "Chat OpenRouter timeouts",
                    {"endpoint": endpoint, "model": selected_model},
                ).inc()
                await self._backoff_delay(idx + 1)
                continue
            except RateLimitError as exc:
                attempts.append(
                    ModelAttempt(
                        model=selected_model,
                        error="Rate limit exceeded (429)",
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )
                if next_model:
                    self._increment_fallback_metric(
                        endpoint, selected_model, next_model, "rate_limit"
                    )
                await self._backoff_delay(idx + 1, retry_after=exc.retry_after)
                continue
            except ServiceUnavailableError:
                attempts.append(
                    ModelAttempt(
                        model=selected_model,
                        error="Service unavailable (503)",
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )
                if next_model:
                    self._increment_fallback_metric(
                        endpoint, selected_model, next_model, "service_unavailable"
                    )
                metrics.counter(
                    "chat_service_unavailable_count",
                    "Chat OpenRouter 503 responses",
                    {"endpoint": endpoint, "model": selected_model},
                ).inc()
                continue
            except OpenRouterError as exc:
                attempts.append(
                    ModelAttempt(
                        model=selected_model,
                        error=str(exc),
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )
                if next_model:
                    self._increment_fallback_metric(
                        endpoint, selected_model, next_model, "openrouter_error"
                    )
                await self._backoff_delay(idx + 1)
                continue

            parsed = self._parse_llm_json(response_text)
            if parsed is None:
                # Log to application logs (not chat logs) with structured data
                logger.debug(
                    "Malformed LLM response for endpoint=%s model=%s",
                    endpoint,
                    selected_model,
                    extra={"raw_response": response_text[:500]},  # Truncate for safety
                )
                attempts.append(
                    ModelAttempt(
                        model=selected_model,
                        error="Malformed JSON response",
                        timestamp=datetime.utcnow().isoformat(),
                    )
                )
                if next_model:
                    self._increment_fallback_metric(
                        endpoint, selected_model, next_model, "parse_error"
                    )
                metrics.counter(
                    "chat_malformed_response_count",
                    "Chat malformed JSON responses",
                    {"endpoint": endpoint, "model": selected_model},
                ).inc()
                parse_failures += 1
                await self._backoff_delay(idx + 1)
                continue

            parsed = self._fill_missing_fields(parsed)
            return parsed, selected_model, False, attempts, raw_response

        if parse_failures > 0:
            fallback = self._safe_fallback(endpoint, last_model)
            return fallback, last_model, True, attempts, raw_response

        metrics.counter(
            "chat_all_models_failed",
            "Chat requests where all models failed",
            {"endpoint": endpoint},
        ).inc()
        raise AllModelsFailed(endpoint, attempts, retry_after=120)

    async def _call_openrouter(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        timeout: float,
        enforce_json: bool,
    ) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        if enforce_json:
            payload["response_format"] = {"type": "json_object"}

        response = await self._post_openrouter(payload, timeout)
        if response.status_code == 400 and enforce_json:
            payload.pop("response_format", None)
            response = await self._post_openrouter(payload, timeout)

        if response.status_code == 429:
            raise RateLimitError(retry_after=self._retry_after_seconds(response))
        if response.status_code == 503:
            raise ServiceUnavailableError()
        if response.status_code >= 400:
            raise OpenRouterError(f"OpenRouter error ({response.status_code})")

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _post_openrouter(self, payload: Dict[str, Any], timeout: float) -> httpx.Response:
        return await self.client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": config.OPENROUTER_REFERER,
            },
            json=payload,
            timeout=timeout,
        )

    def _parse_llm_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        cleaned = response_text.strip()

        # Strip DeepSeek R1 thinking tokens (e.g., <think>...</think>)
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

        # Strip markdown code blocks
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*", "", cleaned).strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()

        def try_parse(text: str) -> Optional[Dict[str, Any]]:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, dict):
                return parsed
            return None

        parsed = try_parse(cleaned)
        if parsed is not None:
            return parsed

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return try_parse(cleaned[start : end + 1])
        return None

    def _fill_missing_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        missing = []
        if not isinstance(data.get("answer"), str) or not data.get("answer"):
            data["answer"] = "Unable to generate answer"
            missing.append("answer")
        if not isinstance(data.get("evidence"), list):
            data["evidence"] = []
            missing.append("evidence")
        if not isinstance(data.get("next_actions"), list):
            data["next_actions"] = []
            missing.append("next_actions")
        if not isinstance(data.get("warnings"), list):
            data["warnings"] = ["LLM response incomplete"]
            missing.append("warnings")
        if missing:
            logger.warning("LLM response missing fields: %s", ", ".join(missing))
        return data

    def _safe_fallback(self, endpoint: str, model: str) -> Dict[str, Any]:
        return {
            "answer": "I encountered an error generating a structured response. Please try rephrasing your question.",
            "evidence": [],
            "next_actions": [],
            "warnings": ["LLM returned malformed response. Falling back to safe response."],
            "model": model,
            "endpoint": endpoint,
        }

    def _resolve_sources(
        self, llm_evidence: List[Dict[str, Any]], retrieved_evidence: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        allowed_types = {"graph", "chunk", "doc"}
        retrieved_by_id = {item["id"]: item for item in retrieved_evidence if item.get("id")}
        resolved: List[Dict[str, Any]] = []

        for item in llm_evidence:
            if not isinstance(item, dict):
                continue
            evidence_id = item.get("id")
            if not evidence_id or not isinstance(evidence_id, str):
                continue
            if not is_valid_urn(evidence_id):
                continue
            item_type = item.get("type")
            if item_type not in allowed_types:
                item_type = retrieved_by_id.get(evidence_id, {}).get("type")
            if item_type not in allowed_types:
                continue
            resolved_item = {
                "type": item_type,
                "id": evidence_id,
                "note": item.get("note") or retrieved_by_id.get(evidence_id, {}).get("note", "Relevant evidence"),
            }
            metadata = item.get("metadata") or retrieved_by_id.get(evidence_id, {}).get("metadata")
            if metadata:
                resolved_item["metadata"] = metadata
            resolved.append(resolved_item)

        if resolved:
            return resolved
        return retrieved_evidence

    def _format_answer(
        self,
        *,
        endpoint: str,
        answer_text: str,
        sources: List[Dict[str, Any]],
        warnings: List[str],
        next_actions: List[str],
        parse_failed: bool,
        raw_candidate: str,
    ) -> str:
        if endpoint == "title":
            return answer_text.strip()

        summary = self._normalize_summary(answer_text)
        sections: List[str] = [f"Summary:\n{summary}"]

        nodes: List[str] = []
        edges: List[str] = []
        chunks: List[str] = []
        docs: List[str] = []

        for source in sources:
            if not isinstance(source, dict):
                continue
            source_type = source.get("type")
            metadata = source.get("metadata") or {}
            urn = source.get("id", "unknown")
            note = source.get("note", "")

            if source_type == "graph":
                rel = metadata.get("relationship")
                if rel:
                    src = metadata.get("source", "unknown")
                    tgt = metadata.get("target", "unknown")
                    edges.append(f"- {src} -{rel}-> {tgt} ({urn})")
                else:
                    label = metadata.get("label", "Node")
                    name = metadata.get("name", note or "unknown")
                    nodes.append(f"- {name} ({label}) ({urn})")
            elif source_type == "chunk":
                file_path = metadata.get("file_path", "unknown")
                chunk_type = metadata.get("chunk_type", "chunk")
                chunks.append(f"- {file_path} ({chunk_type}) ({urn})")
            elif source_type == "doc":
                docs.append(f"- {note or urn}")

        evidence_counts = {
            "nodes": len(nodes),
            "edges": len(edges),
            "chunks": len(chunks),
            "docs": len(docs),
        }
        if any(evidence_counts.values()):
            sections.append(
                "Evidence Summary:\n"
                + "\n".join(
                    [
                        f"- Graph nodes: {evidence_counts['nodes']}",
                        f"- Graph edges: {evidence_counts['edges']}",
                        f"- Vector chunks: {evidence_counts['chunks']}",
                        f"- Documents: {evidence_counts['docs']}",
                    ]
                )
            )

        if warnings:
            sections.append("Warnings:\n" + "\n".join(f"- {w}" for w in warnings))

        cleaned_actions = self._normalize_list(next_actions)
        if cleaned_actions:
            sections.append(
                "Next Actions:\n" + "\n".join(f"- {action}" for action in cleaned_actions)
            )
            sections.append(
                "Suggested Prompts:\n"
                + "\n".join(f"- {self._action_to_prompt(action)}" for action in cleaned_actions)
            )

        if parse_failed and raw_candidate:
            sections.append(
                "Raw Candidate:\n```\n"
                f"{raw_candidate.strip()}\n"
                "```"
            )
        return "\n\n".join(sections)

    def _normalize_summary(self, answer_text: str) -> str:
        if not answer_text:
            return "Unable to generate answer."

        cleaned = answer_text.strip()
        if cleaned.lower().startswith("summary:"):
            cleaned = cleaned.split(":", 1)[1].strip()

        split_markers = [
            "\nGraph Summary:",
            "\nEvidence:",
            "\nNext Actions:",
            "\nWarnings:",
        ]
        for marker in split_markers:
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[0].strip()

        lines = []
        for line in cleaned.splitlines():
            if "urn:li:" in line:
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()

        return cleaned or "Unable to generate answer."

    def _normalize_list(self, items: List[str]) -> List[str]:
        cleaned = []
        seen = set()
        for item in items:
            if not item:
                continue
            normalized = " ".join(str(item).split())
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
        return cleaned

    def _action_to_prompt(self, action: str) -> str:
        if action.endswith("?"):
            return action
        return f"{action}?"

    def _log_chat_event(
        self,
        *,
        endpoint: str,
        query: str,
        project_id: str,
        model: str,
        attempts: List[ModelAttempt],
        warnings: List[str],
        next_actions: List[str],
        latency_seconds: float,
    ) -> None:
        """Log chat event to dedicated JSONL log file."""
        from src.utils.loguru_config import log_to_category

        payload = {
            "endpoint": endpoint,
            "project_id": project_id,
            "model": model,
            "attempts": [
                {"model": attempt.model, "error": attempt.error, "timestamp": attempt.timestamp}
                for attempt in attempts
            ],
            "warnings": warnings,
            "next_actions": next_actions,
            "latency_ms": int(latency_seconds * 1000),
            "query": query,
        }
        log_to_category("chat", payload)

    def _has_graph_sources(self, sources: List[Dict[str, Any]]) -> bool:
        return any(source.get("type") == "graph" for source in sources)

    def _contains_lineage_keywords(self, query: str) -> bool:
        lowered = query.lower()
        return any(keyword in lowered for keyword in LINEAGE_KEYWORDS)

    def _extract_entity_terms(self, query: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_\\.]*", query)
        cleaned = []
        for token in tokens:
            normalized = token.strip().strip(".,")
            if len(normalized) > 3:
                cleaned.append(normalized)
                if normalized.endswith("s") and len(normalized) > 4:
                    cleaned.append(normalized[:-1])
        return list(dict.fromkeys(cleaned))[:15]

    def _build_qdrant_filter(
        self, project_id: Optional[str], repository_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        must = []
        if project_id:
            must.append({"key": "project_id", "match": {"value": project_id}})
        if repository_id:
            must.append({"key": "repository_id", "match": {"value": repository_id}})
        if not must:
            return None
        return {"must": must}

    async def _backoff_delay(self, attempt: int, retry_after: Optional[int] = None) -> None:
        delay = config.CHAT_RETRY_BASE_DELAY_SECONDS * (
            config.CHAT_RETRY_BACKOFF_FACTOR ** (attempt - 1)
        )
        if retry_after:
            delay = max(delay, retry_after)
        if delay > 0:
            await asyncio.sleep(delay)

    def _retry_after_seconds(self, response: httpx.Response) -> Optional[int]:
        retry_after = response.headers.get("Retry-After")
        if not retry_after:
            return None
        try:
            return int(retry_after)
        except ValueError:
            return None

    def _increment_fallback_metric(
        self, endpoint: str, from_model: str, to_model: str, reason: str
    ) -> None:
        metrics.counter(
            "chat_model_fallback_count",
            "Chat model fallback count",
            {
                "endpoint": endpoint,
                "from_model": from_model,
                "to_model": to_model,
                "reason": reason,
            },
        ).inc()

    def _extract_context_ids(
        self, context: Optional[Dict[str, Any]]
    ) -> Tuple[str, Optional[str], Optional[str]]:
        if not context:
            return "default", None, None
        raw_project = context.get("project_id") or context.get("project")
        project_id = str(raw_project or "default")
        repository_id = context.get("repository_id") or context.get("repo_id")
        project_filter = str(raw_project) if raw_project else None
        return project_id, repository_id, project_filter


class RateLimitError(Exception):
    def __init__(self, retry_after: Optional[int] = None):
        super().__init__("OpenRouter rate limit exceeded")
        self.retry_after = retry_after


class ServiceUnavailableError(Exception):
    pass


class OpenRouterError(Exception):
    pass
