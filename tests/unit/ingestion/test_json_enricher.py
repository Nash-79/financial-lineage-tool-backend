import json

from src.ingestion.plugins.json_enricher import JsonEnricherPlugin


def test_json_enricher_extracts_metadata() -> None:
    payload = {"customers": {"owner": "Risk", "sla": "P1", "tags": ["pii"]}}
    plugin = JsonEnricherPlugin()

    result = plugin.parse(json.dumps(payload), {})

    enrichments = result.metadata.get("enrichments", [])
    assert enrichments
    assert enrichments[0]["name"] == "customers"
    assert enrichments[0]["properties"]["owner"] == "Risk"
