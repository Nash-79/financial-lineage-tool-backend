"""
This module contains the GraphExtractor class, which is responsible for
taking parsed code information and translating it into a knowledge graph
format, then ingesting it into Neo4j.
"""

from ..ingestion.code_parser import CodeParser
from .neo4j_client import Neo4jGraphClient
import hashlib
import json
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class GraphExtractor:
    """
    Extracts entities and relationships from parsed code and loads them
    into a Neo4j graph database with batched operations for performance.
    """

    def __init__(
        self,
        neo4j_client: Neo4jGraphClient,
        code_parser: CodeParser,
        enable_batching: bool = True,
        batch_size: int = 100,
    ):
        """
        Initialize GraphExtractor with optional batch processing.

        Args:
            neo4j_client: Neo4j client instance
            code_parser: Code parser instance
            enable_batching: Enable batch processing (default: True)
            batch_size: Max entities/relationships per batch (default: 100)
        """
        self.client = neo4j_client
        self.parser = code_parser
        self.enable_batching = enable_batching
        self.batch_size = batch_size

        # Batch accumulators
        self._entity_batch: List[Dict[str, Any]] = []
        self._relationship_batch: List[Dict[str, Any]] = []

    def _generate_id(self, *parts):
        """Creates a deterministic ID from a set of parts."""
        m = hashlib.sha256()
        for part in parts:
            m.update(str(part).encode("utf-8"))
        return m.hexdigest()

    def _add_entity_to_batch(self, entity_id: str, entity_type: str, **properties):
        """
        Add entity to batch or write immediately if batching disabled.

        Args:
            entity_id: Entity ID
            entity_type: Entity type/label
            **properties: Additional entity properties
        """
        entity_data = {"id": entity_id, "entity_type": entity_type, **properties}

        if self.enable_batching:
            self._entity_batch.append(entity_data)
            # Auto-flush if batch size reached
            if len(self._entity_batch) >= self.batch_size:
                self._flush_entities()
        else:
            # Fallback to individual write
            self.client.add_entity(
                entity_id=entity_id, entity_type=entity_type, **properties
            )

    def _add_relationship_to_batch(
        self, source_id: str, target_id: str, relationship_type: str, **properties
    ):
        """
        Add relationship to batch or write immediately if batching disabled.

        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            relationship_type: Relationship type
            **properties: Additional relationship properties
        """
        rel_data = {
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            **properties,
        }

        if self.enable_batching:
            self._relationship_batch.append(rel_data)
            # Auto-flush if batch size reached
            if len(self._relationship_batch) >= self.batch_size:
                self._flush_relationships()
        else:
            # Fallback to individual write
            self.client.add_relationship(
                source_id, target_id, relationship_type, **properties
            )

    def _flush_entities(self):
        """Flush accumulated entities to Neo4j using batch operations."""
        if not self._entity_batch:
            return

        count = len(self._entity_batch)
        logger.debug(f"Flushing {count} entities to Neo4j")

        try:
            created = self.client.batch_create_entities(
                entities=self._entity_batch, batch_size=self.batch_size
            )
            logger.info(f"Successfully flushed {created}/{count} entities")
        except Exception as e:
            logger.error(f"Failed to flush entities: {e}")
            raise
        finally:
            # Clear batch regardless of success/failure
            self._entity_batch.clear()

    def _flush_relationships(self):
        """Flush accumulated relationships to Neo4j using batch operations."""
        if not self._relationship_batch:
            return

        count = len(self._relationship_batch)
        logger.debug(f"Flushing {count} relationships to Neo4j")

        try:
            created = self.client.batch_create_relationships(
                relationships=self._relationship_batch, batch_size=self.batch_size
            )
            logger.info(f"Successfully flushed {created}/{count} relationships")
        except Exception as e:
            logger.error(f"Failed to flush relationships: {e}")
            raise
        finally:
            # Clear batch regardless of success/failure
            self._relationship_batch.clear()

    def flush_batch(self):
        """
        Manually flush all accumulated entities and relationships to Neo4j.

        This should be called after processing a batch of files to ensure
        all pending writes are committed to the database.
        """
        logger.debug("Manual batch flush requested")
        self._flush_entities()
        self._flush_relationships()
        logger.info("Batch flush complete")

    def ingest_sql_lineage(
        self, sql_content: str, dialect: str = "tsql", source_file: str = "unknown"
    ):
        """
        Parses a SQL script and ingests the resulting lineage into Neo4j.
        This method orchestrates the parsing and graph creation process.

        Args:
            sql_content: The SQL script to process.
            dialect: The SQL dialect of the script.
            source_file: The name of the file this SQL came from.
        """
        parsed_data = self.parser.parse_sql(sql_content, dialect=dialect)

        if not parsed_data:
            print(f"Skipping ingestion for {source_file} as parsing yielded no data.")
            return

        # 1. Ingest Data Assets (Tables, Views)
        write_asset_id = None
        if parsed_data.get("write") and parsed_data["write"] != "console":
            write_asset_id = self._generate_id("data_asset", parsed_data["write"])
            asset_type = (
                "View"
                if parsed_data["write"] in parsed_data.get("views", [])
                else "Table"
            )
            self._add_entity_to_batch(
                entity_id=write_asset_id,
                entity_type=asset_type,
                name=parsed_data["write"],
                source_file=source_file,
            )

        read_asset_ids = {}
        for asset_name in parsed_data.get("read", []):
            asset_id = self._generate_id("data_asset", asset_name)
            read_asset_ids[asset_name] = asset_id
            self._add_entity_to_batch(
                entity_id=asset_id,
                entity_type="DataAsset",  # Generic type, could be table or view
                name=asset_name,
                source_file=source_file,
            )

        # 2. Ingest Column-Level Lineage
        for col_lineage in parsed_data.get("columns", []):
            target_col_name = col_lineage["target"]

            # We need to associate the target column with the write asset
            if not write_asset_id:
                continue

            target_col_id = self._generate_id(
                "column", parsed_data["write"], target_col_name
            )
            self._add_entity_to_batch(
                entity_id=target_col_id, entity_type="Column", name=target_col_name
            )
            # Link column to its parent asset
            self._add_relationship_to_batch(write_asset_id, target_col_id, "CONTAINS")

            # Create transformation node
            transformation_logic = col_lineage["transformation"]
            trans_id = self._generate_id(
                "transformation", transformation_logic, target_col_id
            )
            self._add_entity_to_batch(
                entity_id=trans_id,
                entity_type="Transformation",
                logic=transformation_logic,
            )
            # Link transformation to the target column it generates
            self._add_relationship_to_batch(trans_id, target_col_id, "GENERATES")

            # Link source columns to the transformation
            for source_col_full_name in col_lineage["sources"]:
                # Simple split, may need more robust parsing for complex names
                parts = source_col_full_name.split(".")
                source_table_name = parts[0] if len(parts) > 1 else "unknown"
                source_col_name = parts[-1]

                source_asset_id = read_asset_ids.get(source_table_name)
                if not source_asset_id:
                    # If the source asset wasn't in the main "read" list, add it now
                    source_asset_id = self._generate_id("data_asset", source_table_name)
                    self._add_entity_to_batch(
                        entity_id=source_asset_id,
                        entity_type="DataAsset",
                        name=source_table_name,
                    )
                    read_asset_ids[source_table_name] = source_asset_id

                source_col_id = self._generate_id(
                    "column", source_table_name, source_col_name
                )
                self._add_entity_to_batch(
                    entity_id=source_col_id, entity_type="Column", name=source_col_name
                )
                self._add_relationship_to_batch(
                    source_asset_id, source_col_id, "CONTAINS"
                )
                self._add_relationship_to_batch(source_col_id, trans_id, "INPUT_TO")

        # 3. Ingest Functions and Procedures
        for func_name in parsed_data.get("functions_and_procedures", []):
            func_id = self._generate_id("function", func_name)
            self._add_entity_to_batch(
                entity_id=func_id,
                entity_type="FunctionOrProcedure",
                name=func_name,
                source_file=source_file,
            )

        print(f"Successfully ingested lineage from {source_file}.")

    def ingest_file(self, file_path: str):
        """
        Ingests a file based on its extension.

        Args:
            file_path: Absolute or relative path to the file.
        """
        if not os.path.exists(file_path):
            print(f"[!] File not found: {file_path}")
            return

        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()

        # Create File Node
        file_id = self._generate_id("file", file_path)
        self._add_entity_to_batch(
            entity_id=file_id,
            entity_type="File",
            name=filename,
            path=file_path,
            extension=ext,
        )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            if ext == ".sql":
                print(f"[*] Ingesting SQL: {filename}")
                # Use existing logic, but maybe we can link assets to this file node?
                # For now, just call the existing method.
                self.ingest_sql_lineage(content, source_file=filename)

            elif ext == ".py":
                print(f"[*] Ingesting Python: {filename}")
                self.ingest_python(content, source_file=filename, file_node_id=file_id)

            elif ext == ".json":
                print(f"[*] Ingesting JSON: {filename}")
                self.ingest_json(content, source_file=filename, file_node_id=file_id)

            else:
                print(f"[i] Skipping unsupported file type: {ext}")

        except Exception as e:
            print(f"[!] Error processing {file_path}: {e}")

    def ingest_python(self, content: str, source_file: str, file_node_id: str = None):
        """Ingest Python structure."""
        parsed = self.parser.parse_python(content)
        if not parsed:
            return

        # Ingest Classes
        for cls in parsed["classes"]:
            cls_id = self._generate_id("class", cls["name"], source_file)
            self._add_entity_to_batch(
                entity_id=cls_id,
                entity_type="Class",
                name=cls["name"],
                docstring=cls["docstring"] or "",
            )
            if file_node_id:
                self._add_relationship_to_batch(file_node_id, cls_id, "DEFINES")

            # Bases
            for base in cls["bases"]:
                # We assume base is a known name, we can try to link if it exists unique
                # For now, just a property or a tentative node
                pass

        # Ingest Functions
        for func in parsed["functions"]:
            func_id = self._generate_id("function", func["name"], source_file)
            self._add_entity_to_batch(
                entity_id=func_id,
                entity_type="Function",
                name=func["name"],
                args=json.dumps(func["args"]),
                docstring=func["docstring"] or "",
            )
            if file_node_id:
                self._add_relationship_to_batch(file_node_id, func_id, "DEFINES")

        # Ingest Imports
        for imp in parsed["imports"]:
            # Maybe link to a Module node
            mod_id = self._generate_id("module", imp)
            self._add_entity_to_batch(entity_id=mod_id, entity_type="Module", name=imp)
            if file_node_id:
                self._add_relationship_to_batch(file_node_id, mod_id, "IMPORTS")

    def ingest_json(self, content: str, source_file: str, file_node_id: str = None):
        """Ingest JSON structure."""
        parsed = self.parser.parse_json(content)
        if not parsed:
            return

        json_id = self._generate_id("json_doc", source_file)
        self._add_entity_to_batch(
            entity_id=json_id,
            entity_type="JsonDocument",
            name=source_file,
            root_type=parsed["type"],
            key_count=len(parsed["keys"]),
            array_len=parsed["array_length"],
        )
        if file_node_id:
            self._add_relationship_to_batch(file_node_id, json_id, "CONTAINS_CONTENT")

        # Add keys as nodes if dict
        for key in parsed["keys"]:
            key_id = self._generate_id("json_key", source_file, key)
            self._add_entity_to_batch(entity_id=key_id, entity_type="JsonKey", name=key)
            self._add_relationship_to_batch(json_id, key_id, "HAS_KEY")


if __name__ == "__main__":
    # This is an example of how to use the extractor.
    # It requires a running Neo4j instance and a .env file.
    import os
    from dotenv import load_dotenv

    load_dotenv(dotenv_path="../../.env")

    try:
        neo4j_client = Neo4jGraphClient(
            uri=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            database=os.getenv("NEO4J_DATABASE"),
        )
        code_parser = CodeParser()
        extractor = GraphExtractor(neo4j_client, code_parser)

        print("--- Ingesting Example 1: CREATE TABLE AS SELECT ---")
        sql1 = """
        CREATE TABLE target_db.dbo.fact_sales AS
        SELECT
            s.sale_id as sale_identifier,
            p.product_name,
            c.customer_name,
            CAST(s.sale_date AS DATE) as event_date,
            s.quantity * p.price as total_amount
        FROM staging.sales s
        JOIN staging.products p ON s.product_id = p.product_id
        JOIN staging.customers c ON s.customer_id = c.customer_id
        WHERE s.status = 'COMPLETED';
        """
        extractor.ingest_sql_lineage(
            sql1, dialect="duckdb", source_file="sales_etl.sql"
        )

        print("\n--- Ingesting Example 2: CREATE VIEW ---")
        sql2 = """
        CREATE VIEW reporting.vw_customer_summary AS
        SELECT
            customer_id,
            COUNT(order_id) as number_of_orders,
            SUM(total_amount) as total_spent
        FROM fact_orders
        GROUP BY 1;
        """
        extractor.ingest_sql_lineage(
            sql2, dialect="tsql", source_file="reporting_views.sql"
        )

        # Flush any remaining batched entities and relationships
        print("\n--- Flushing batch ---")
        extractor.flush_batch()

        # Clean up and close connection
        # In a real scenario you might not want to clear the graph
        # print("\n--- Clearing graph for demo purposes ---")
        # neo4j_client.query("MATCH (n) DETACH DELETE n")
        neo4j_client.close()
        print("\n--- Demo Complete ---")

    except Exception as e:
        print(f"An error occurred during the demo: {e}")
        print("Please ensure your .env file is set up correctly and Neo4j is running.")
