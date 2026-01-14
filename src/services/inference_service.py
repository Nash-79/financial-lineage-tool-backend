"""OpenRouter-based lineage inference service with free-tier enforcement."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from src.llm.free_tier import DEFAULT_FREE_TIER_MODEL, enforce_free_tier
from src.models.inference import LineageEdgeProposal

logger = logging.getLogger(__name__)


class OpenRouterService:
    """Dedicated OpenRouter client for lineage inference."""

    def __init__(
        self,
        api_key: str,
        default_model: str = DEFAULT_FREE_TIER_MODEL,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterService")
        self.api_key = api_key
        self.default_model = default_model
        self.client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def predict_lineage(
        self,
        code_snippet: str,
        context_nodes: list[str],
        model: Optional[str] = None,
        prompt_override: Optional[str] = None,
    ) -> list[LineageEdgeProposal]:
        """Predict lineage edges using OpenRouter."""
        selected_model = self._select_model(model or self.default_model)
        prompt = prompt_override or self.build_lineage_prompt(
            code_snippet, context_nodes
        )

        response = await self._call_openrouter(prompt=prompt, model=selected_model)
        if not response:
            return []

        edges = response.get("edges", [])
        proposals: list[LineageEdgeProposal] = []
        for edge in edges:
            try:
                proposals.append(LineageEdgeProposal(**edge))
            except Exception as exc:
                logger.warning("Invalid edge proposal skipped: %s", exc)
        return proposals

    def _select_model(self, model: str) -> str:
        """Ensure model is on the free tier."""
        selected_model, downgraded = enforce_free_tier(model)
        if downgraded:
            logger.warning(
                "Downgrading model '%s' to free tier model '%s'",
                model,
                DEFAULT_FREE_TIER_MODEL,
            )
        return selected_model

    async def _call_openrouter(
        self, *, prompt: str, model: str
    ) -> Optional[dict[str, Any]]:
        """Call OpenRouter with strict JSON mode and fallback when unsupported."""
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only JSON. "
                        "Respond with an object containing an 'edges' array."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        try:
            response = await self.client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-repo",
                },
                json=payload,
            )
            if response.status_code == 400:
                logger.warning(
                    "OpenRouter 400 for model %s, retrying without response_format: %s",
                    model,
                    response.text,
                )
                fallback_payload = dict(payload)
                fallback_payload.pop("response_format", None)
                response = await self.client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/your-repo",
                    },
                    json=fallback_payload,
                )
            if response.status_code == 429:
                logger.warning("OpenRouter rate limit hit for model %s", model)
                return None
            if response.status_code == 503:
                logger.warning("OpenRouter unavailable for model %s", model)
                return None
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("OpenRouter returned non-JSON response: %s", exc)
            return None
        except httpx.HTTPError as exc:
            logger.error("OpenRouter request failed: %s", exc)
            return None

    def build_lineage_prompt(self, code_snippet: str, context_nodes: list[Any]) -> str:
        """Build the lineage inference prompt."""
        context_json = json.dumps(context_nodes, indent=2)
        return (
            "You are a knowledge graph enrichment agent. "
            "Analyze the code and propose lineage edges.\n\n"
            "Code:\n"
            f"{code_snippet}\n\n"
            "Context Nodes:\n"
            f"{context_json}\n\n"
            "Use only node ids from the context list.\n\n"
            "Return JSON like:\n"
            "{\n"
            '  "edges": [\n'
            "    {\n"
            '      "source_node": "urn:li:data_asset:project:source_table",\n'
            '      "target_node": "urn:li:data_asset:project:target_table",\n'
            '      "relationship_type": "READS|WRITES",\n'
            '      "confidence": 0.0,\n'
            '      "reasoning": "string"\n'
            "    }\n"
            "  ]\n"
            "}"
        )
