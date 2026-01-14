from src.ingestion.plugins.python_treesitter import PythonTreesitterPlugin


def test_treesitter_handles_syntax_error() -> None:
    plugin = PythonTreesitterPlugin(prefer_ast_for_small_files=False)
    content = "def broken(:\n    pass\n"

    result = plugin.parse(content, {})

    assert result.metadata.get("parser") == "treesitter"
