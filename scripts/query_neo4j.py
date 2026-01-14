"""
Query and visualize Neo4j graph data.
(Wrapper for src.utils.diagnostics)
"""

import sys
import os

# Ensure src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.diagnostics import GraphInspector

if __name__ == "__main__":
    inspector = GraphInspector()
    try:
        inspector.run_diagnostics()
    except Exception as e:
        print(f"[!] Error: {e}")
        sys.exit(1)
