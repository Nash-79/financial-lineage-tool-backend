"""Plugin registry and loader for lineage parsers."""

from __future__ import annotations

import importlib
import json
import logging
import os
from typing import Any, Dict, List, Optional, Type

from .plugins.base import LineagePlugin

logger = logging.getLogger(__name__)

DEFAULT_PLUGIN_PATHS = [
    "src.ingestion.plugins.sql_standard.StandardSqlPlugin",
    "src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin",
    "src.ingestion.plugins.json_enricher.JsonEnricherPlugin",
]


class PluginRegistry:
    """Registry for parser plugins."""

    def __init__(self) -> None:
        self._plugins: List[LineagePlugin] = []

    def register(self, plugin: LineagePlugin) -> None:
        self._plugins.append(plugin)

    def list_plugins(self) -> List[LineagePlugin]:
        return list(self._plugins)

    def get_for_extension(self, extension: str) -> Optional[LineagePlugin]:
        ext = extension.lower()
        for plugin in self._plugins:
            if ext in [e.lower() for e in plugin.supported_extensions]:
                return plugin
        return None


class PluginLoader:
    """Loads plugins from module paths and configuration."""

    def __init__(self, plugin_paths: List[str], config: Dict[str, Any]) -> None:
        self.plugin_paths = plugin_paths
        self.config = config

    def load(self) -> PluginRegistry:
        registry = PluginRegistry()
        for path in self.plugin_paths:
            try:
                plugin_class = self._import_class(path)
                plugin_config = self.config.get(path, {})
                plugin = self._instantiate(plugin_class, plugin_config)
                registry.register(plugin)
                logger.info("Registered plugin: %s", path)
            except Exception as exc:
                logger.warning("Failed to load plugin %s: %s", path, exc)
        return registry

    def _import_class(self, path: str) -> Type[LineagePlugin]:
        module_path, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    def _instantiate(
        self, plugin_class: Type[LineagePlugin], config: Dict[str, Any]
    ) -> LineagePlugin:
        try:
            return plugin_class(**config)
        except TypeError:
            return plugin_class()


def load_plugins_from_env() -> PluginRegistry:
    """Load plugins from environment variables."""
    raw_paths = os.getenv("LINEAGE_PLUGINS", "").strip()
    if raw_paths:
        plugin_paths = [p.strip() for p in raw_paths.split(",") if p.strip()]
    else:
        plugin_paths = DEFAULT_PLUGIN_PATHS

    raw_config = os.getenv("LINEAGE_PLUGIN_CONFIG_JSON", "").strip()
    config: Dict[str, Any] = {}
    if raw_config:
        try:
            config = json.loads(raw_config)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid LINEAGE_PLUGIN_CONFIG_JSON: %s", exc)

    return PluginLoader(plugin_paths, config).load()
