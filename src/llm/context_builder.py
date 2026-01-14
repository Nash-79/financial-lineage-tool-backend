"""
Project context builder for LLM prompt injection.

This module provides utilities to build the <project_context> block
that gets prepended to LLM prompts during entity extraction.
"""

from typing import Optional
from src.storage.metadata_store import ProjectStore


def build_context_block(project_id: Optional[str]) -> str:
    """
    Build the <project_context> XML block for LLM prompt injection.

    Args:
        project_id: Project ID to fetch context for

    Returns:
        XML-formatted context block string, or empty string if no context
    """
    if not project_id:
        return ""

    project_store = ProjectStore()
    context = project_store.get_context(project_id)

    if not context or not context.get("description"):
        return ""

    # Build XML block
    lines = ["<project_context>"]

    # Description
    if context.get("description"):
        lines.append(f"  <description>{context['description']}</description>")

    # Format
    if context.get("format"):
        lines.append(f"  <format>{context['format']}</format>")

    # Source entities (starting points)
    source_entities = context.get("source_entities", [])
    if source_entities:
        entities_str = ", ".join(source_entities)
        lines.append(f"  <source_entities>{entities_str}</source_entities>")

    # Target entities (endpoints)
    target_entities = context.get("target_entities", [])
    if target_entities:
        entities_str = ", ".join(target_entities)
        lines.append(f"  <target_entities>{entities_str}</target_entities>")

    # Domain hints
    domain_hints = context.get("domain_hints", [])
    if domain_hints:
        hints_str = ", ".join(domain_hints)
        lines.append(f"  <domain_hints>{hints_str}</domain_hints>")

    lines.append("</project_context>")

    return "\n".join(lines)


def inject_context_into_prompt(prompt: str, project_id: Optional[str]) -> str:
    """
    Inject project context at the beginning of an LLM prompt.

    Args:
        prompt: Original prompt string
        project_id: Project ID to fetch context for

    Returns:
        Prompt with context block prepended (if context exists)
    """
    context_block = build_context_block(project_id)

    if not context_block:
        return prompt

    return f"{context_block}\n\n{prompt}"
