from src.ingestion.plugins.sql_standard import StandardSqlPlugin


def test_sql_plugin_parses_write_and_reads() -> None:
    plugin = StandardSqlPlugin()
    sql = "CREATE TABLE sales AS SELECT * FROM staging.orders;"

    result = plugin.parse(sql, {"dialect": "duckdb"})

    names = {node.name for node in result.nodes}
    assert "sales" in names
    assert "staging.orders" in names
    assert "staging.orders" in result.external_refs
    assert any(edge.relationship in {"READS_FROM", "DERIVES"} for edge in result.edges)
