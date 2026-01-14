"""JSON enrichment plugin for metadata application."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from .base import LineagePlugin, LineageResult

logger = logging.getLogger(__name__)


class JsonEnricherPlugin(LineagePlugin):
    """Parse JSON metadata files and return enrichment payloads."""

    ENRICHMENT_FIELDS = {"owner", "sla", "description", "tags"}

    def __init__(self, allow_node_creation: bool = False) -> None:
        self.allow_node_creation = allow_node_creation

    @property
    def supported_extensions(self) -> List[str]:
        return [".json"]

    def parse(self, content: str, context: Dict[str, Any]) -> LineageResult:
        try:
            data = json.loads(content)
        except Exception as exc:
            logger.warning("JSON parsing failed: %s", exc)
            return LineageResult(metadata={"parsed": None, "enrichments": []})

        enrichments = self._extract_enrichments(data)
        parsed = self._summarize_json(data)
        return LineageResult(
            nodes=[],
            edges=[],
            external_refs=[],
            metadata={"enrichments": enrichments, "parsed": parsed},
        )

    def _summarize_json(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, dict):
            return {
                "type": "dict",
                "keys": list(data.keys()),
                "array_length": 0,
            }
        if isinstance(data, list):
            return {
                "type": "list",
                "keys": (
                    list(data[0].keys()) if data and isinstance(data[0], dict) else []
                ),
                "array_length": len(data),
            }
        return {
            "type": type(data).__name__,
            "keys": [],
            "array_length": 0,
        }

    def _extract_enrichments(self, data: Any) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []

        if isinstance(data, list):
            entries = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            if isinstance(data.get("entities"), list):
                entries = [item for item in data["entities"] if isinstance(item, dict)]
            elif isinstance(data.get("tables"), list):
                entries = [item for item in data["tables"] if isinstance(item, dict)]
            else:
                entries = [
                    {"name": key, **value}
                    for key, value in data.items()
                    if isinstance(value, dict)
                ]

        enrichments: List[Dict[str, Any]] = []
        for entry in entries:
            name = (
                entry.get("name")
                or entry.get("table")
                or entry.get("table_name")
                or entry.get("id")
            )
            if not name:
                continue
            properties = {k: entry.get(k) for k in self.ENRICHMENT_FIELDS if k in entry}
            if not properties:
                continue
            enrichments.append({"name": name, "properties": properties})

        return enrichments
