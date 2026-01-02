"""
CPU-Bound Parser - ProcessPoolExecutor-compatible SQL parsing functions.

This module provides standalone parsing functions that can be executed in separate
processes via ProcessPoolExecutor to avoid blocking the asyncio event loop with
CPU-intensive regex operations.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def parse_sql_file(file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse SQL file and extract database objects (CPU-intensive operation).

    This function is designed to be executed in a ProcessPoolExecutor and must be
    picklable (no instance methods or closures).

    Args:
        file_path: Path to SQL file

    Returns:
        Dictionary mapping object types to lists of parsed objects
        Example: {
            'tables': [{'name': 'users', 'sql': '...'}],
            'views': [{'name': 'user_view', 'sql': '...'}]
        }
    """
    try:
        # Import here to avoid pickling issues
        from src.parsing.enhanced_sql_parser import EnhancedSQLParser
        from src.parsing.code_parser import CodeParser

        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Initialize parser (no cache in process pool to avoid sharing issues)
        parser = EnhancedSQLParser(cache=None)
        code_parser = CodeParser()

        # Parse SQL file (CPU-intensive regex operations)
        parsed_results = parser.parse_sql_file(content, str(file_path))

        # Organize by type
        results = {
            "tables": [],
            "views": [],
            "procedures": [],
            "functions": [],
            "triggers": [],
        }

        for obj in parsed_results:
            obj_type = obj.get("type", "").lower()
            if obj_type == "table":
                results["tables"].append(obj)
            elif obj_type == "view":
                results["views"].append(obj)
            elif obj_type == "procedure":
                results["procedures"].append(obj)
            elif obj_type == "function":
                results["functions"].append(obj)
            elif obj_type == "trigger":
                results["triggers"].append(obj)

        logger.debug(
            f"Parsed {file_path}: {sum(len(v) for v in results.values())} objects"
        )
        return results

    except Exception as e:
        logger.error(f"Error parsing {file_path} in process pool: {e}")
        return {}


def parse_sql_files_batch(file_paths: List[str]) -> List[Dict[str, Any]]:
    """
    Parse multiple SQL files in a single process worker.

    This reduces process spawn overhead by processing multiple files per process.

    Args:
        file_paths: List of file paths to parse

    Returns:
        List of (file_path, results) tuples
    """
    results = []

    for file_path in file_paths:
        try:
            parsed = parse_sql_file(file_path)
            results.append(
                {
                    "file_path": file_path,
                    "success": True,
                    "results": parsed,
                    "error": None,
                }
            )
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            results.append(
                {
                    "file_path": file_path,
                    "success": False,
                    "results": {},
                    "error": str(e),
                }
            )

    return results


# Example usage for testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python cpu_bound_parser.py <sql_file>")
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"Parsing: {file_path}")

    results = parse_sql_file(file_path)

    print("\nParsed Objects:")
    for obj_type, objects in results.items():
        if objects:
            print(f"  {obj_type}: {len(objects)}")
            for obj in objects:
                print(f"    - {obj.get('name', 'unnamed')}")
