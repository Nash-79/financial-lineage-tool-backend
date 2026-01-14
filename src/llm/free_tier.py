"""Shared free-tier model enforcement for cloud LLM providers."""

from __future__ import annotations

from typing import Optional, Tuple


DEFAULT_FREE_TIER_MODEL = "google/gemini-2.0-flash-exp:free"
FREE_TIER_MODELS = {
    "google/gemini-2.0-flash-exp:free",
    "mistralai/mistral-7b-instruct:free",
    "mistralai/devstral-2512:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "deepseek/deepseek-r1:free",
}


def enforce_free_tier(model: Optional[str]) -> Tuple[str, bool]:
    """Return a free-tier model and whether a downgrade occurred."""
    if not model:
        return DEFAULT_FREE_TIER_MODEL, False
    if model in FREE_TIER_MODELS:
        return model, False
    return DEFAULT_FREE_TIER_MODEL, True
