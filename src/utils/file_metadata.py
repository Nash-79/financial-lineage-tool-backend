"""
Utilities for file metadata normalization and safe path handling.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing path components and unsafe characters.
    """
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w\-_\.]", "_", filename)
    filename = filename.lstrip(".")
    return filename or "unnamed_file"


def sanitize_relative_path(path_value: str) -> str:
    """
    Sanitize a relative path while preserving directory structure.

    Removes absolute anchors and path traversal segments.
    """
    path = Path(path_value)
    anchor = path.anchor
    parts = []
    for part in path.parts:
        if part in ("", ".", "..", os.sep, os.altsep, anchor):
            continue
        parts.append(sanitize_filename(part))
    return "/".join(parts) or "unnamed_file"


def infer_file_type(path_value: str) -> str:
    """
    Infer normalized file type from a path or filename.
    """
    ext = Path(path_value).suffix.lower().lstrip(".")
    if ext == "py":
        return "python"
    if ext:
        return ext
    return "unknown"
