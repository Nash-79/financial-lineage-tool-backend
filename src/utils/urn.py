"""URN utilities for lineage entity identifiers."""

from __future__ import annotations

import re
from typing import Dict


URN_SCHEME = "urn"
URN_NAMESPACE = "li"


def normalize_asset_path(asset_path: str) -> str:
    """Normalize asset paths for URN construction."""
    if asset_path is None:
        return ""
    normalized = str(asset_path).strip()
    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.strip("/")


def generate_urn(entity_type: str, project_id: str, asset_path: str) -> str:
    """Generate a URN for a lineage entity."""
    entity = (entity_type or "unknown").strip()
    project = (project_id or "default").strip()
    asset = normalize_asset_path(asset_path) or "unknown"
    return f"{URN_SCHEME}:{URN_NAMESPACE}:{entity}:{project}:{asset}"


def parse_urn(urn: str) -> Dict[str, str]:
    """Parse a URN string into its components."""
    if not urn:
        raise ValueError("URN is empty")
    parts = urn.split(":", 4)
    if len(parts) != 5:
        raise ValueError(f"Invalid URN format: {urn}")
    scheme, namespace, entity_type, project_id, asset_path = parts
    if scheme != URN_SCHEME or namespace != URN_NAMESPACE:
        raise ValueError(f"Invalid URN prefix: {urn}")
    return {
        "scheme": scheme,
        "namespace": namespace,
        "entity_type": entity_type,
        "project_id": project_id,
        "asset_path": asset_path,
    }


def is_valid_urn(urn: str) -> bool:
    """Return True when the URN is syntactically valid."""
    try:
        parse_urn(urn)
    except ValueError:
        return False
    return True
