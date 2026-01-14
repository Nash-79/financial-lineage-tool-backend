"""Base classes for lineage parser plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Node:
    """Standardized node representation for plugin outputs."""

    name: str
    label: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Standardized edge representation for plugin outputs."""

    source: str
    target: str
    relationship: str
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageResult:
    """Standardized plugin output structure."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    external_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LineagePlugin(ABC):
    """Abstract base class for lineage parser plugins."""

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """File extensions supported by this plugin."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, content: str, context: Dict[str, Any]) -> LineageResult:
        """Parse content and return standardized lineage result."""
        raise NotImplementedError
