"""Shared free-tier model enforcement for cloud LLM providers."""

from __future__ import annotations

from typing import Optional, Tuple

from src.api.config import config


DEFAULT_FREE_TIER_MODEL = config.DEFAULT_FREE_TIER_MODEL
FREE_TIER_MODELS = set(config.FREE_TIER_MODELS) | {"qwen/qwen3-4b:free"}


def enforce_free_tier(model: Optional[str]) -> Tuple[str, bool]:
    """Return a free-tier model and whether a downgrade occurred."""
    if not model:
        return DEFAULT_FREE_TIER_MODEL, False
    if model in FREE_TIER_MODELS:
        return model, False
    return DEFAULT_FREE_TIER_MODEL, True
