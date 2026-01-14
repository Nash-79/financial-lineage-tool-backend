# Plugin Development Guide

This guide explains how to build and register lineage parser plugins.

## Overview

Plugins implement a standard interface and return a `LineageResult` with nodes, edges, and external references.

## Plugin Interface

```python
from src.ingestion.plugins.base import LineagePlugin, LineageResult


class MyPlugin(LineagePlugin):
    @property
    def supported_extensions(self) -> list[str]:
        return [".ext"]

    def parse(self, content: str, context: dict) -> LineageResult:
        ...
```

## Registering Plugins

Add your plugin to `.env`:

```bash
LINEAGE_PLUGINS=src.ingestion.plugins.sql_standard.StandardSqlPlugin,src.ingestion.plugins.python_treesitter.PythonTreesitterPlugin,src.ingestion.plugins.json_enricher.JsonEnricherPlugin,src.ingestion.plugins.my_plugin.MyPlugin
```

Optional configuration can be passed via JSON:

```bash
LINEAGE_PLUGIN_CONFIG_JSON={"src.ingestion.plugins.my_plugin.MyPlugin":{"custom_flag":true}}
```

## Output Structure

`LineageResult` must contain:
- `nodes`: list of Node(name, label, type, properties)
- `edges`: list of Edge(source, target, relationship, properties)
- `external_refs`: referenced assets not defined in the file
- `metadata`: plugin-specific metadata

## Testing

Add tests under `tests/unit/ingestion/`:

```bash
pytest tests/unit/ingestion/test_my_plugin.py
```

Ensure tests cover:
- Supported extensions
- Parsing success path
- Error handling for malformed files

## Tips

- Use `context["dialect"]` for SQL dialect hints.
- Keep parsing pure; avoid side effects.
- Return partial results if parsing fails.
