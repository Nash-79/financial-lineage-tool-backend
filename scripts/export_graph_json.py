"""
Export Neo4j graph data to JSON format.
(Wrapper for src.utils.exporters)
"""

import sys
import os

# Ensure src is in pythonpath
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.exporters import (
    export_graph_to_json,
    export_graph_for_visualization,
    export_cypher_queries,
)

if __name__ == "__main__":
    print(
        """
    ================================================================
              Neo4j Graph Export to JSON
    ================================================================
    """
    )
    try:
        # Export full graph
        print("\n[1] Exporting full graph data...")
        export_graph_to_json("data/graph_export.json")

        # Export visualization format
        print("\n[2] Exporting visualization format...")
        export_graph_for_visualization("data/graph_viz.json")

        # Export Cypher queries
        print("\n[3] Exporting Cypher queries...")
        export_cypher_queries("data/cypher_queries.json")

        print("\n" + "=" * 64)
        print("[+] All exports completed successfully!")
        print("=" * 64)

    except Exception as e:
        print(f"\n[!] Error: {e}")
        sys.exit(1)
