"""Validate that local documentation links resolve to existing files."""

from __future__ import annotations

import re
from pathlib import Path


LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _is_external(link: str) -> bool:
    return link.startswith(
        ("http://", "https://", "mailto:", "tel:", "ws://", "wss://")
    )


def test_docs_links_resolve():
    repo_root = Path(__file__).resolve().parents[2]
    docs_root = repo_root / "docs"
    missing = []

    for doc_path in docs_root.rglob("*.md"):
        content = doc_path.read_text(encoding="utf-8")
        content = re.sub(r"```[\s\S]*?```", "", content)
        for match in LINK_PATTERN.findall(content):
            link = match.strip().strip("<>")
            if not link or link.startswith("#") or _is_external(link):
                continue

            link_path = link.split("#", 1)[0]
            if not link_path:
                continue

            if link_path.startswith("/"):
                candidate = repo_root / link_path.lstrip("/")
            else:
                candidate = doc_path.parent / link_path

            if not candidate.exists():
                missing.append(f"{doc_path}: {link}")

    assert not missing, "Broken doc links:\n" + "\n".join(missing)
