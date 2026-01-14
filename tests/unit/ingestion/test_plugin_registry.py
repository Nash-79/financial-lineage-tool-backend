from src.ingestion.plugin_registry import PluginRegistry
from src.ingestion.plugins.sql_standard import StandardSqlPlugin


def test_registry_selects_plugin_by_extension() -> None:
    registry = PluginRegistry()
    registry.register(StandardSqlPlugin())

    plugin = registry.get_for_extension(".sql")

    assert isinstance(plugin, StandardSqlPlugin)
