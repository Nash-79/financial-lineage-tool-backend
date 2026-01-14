"""
This module contains the GraphExtractor class, which is responsible for
taking parsed code information and translating it into a knowledge graph
format, then ingesting it into Neo4j.
"""

from ..ingestion.code_parser import CodeParser
from ..ingestion.plugins.base import LineageResult
from ..utils.urn import generate_urn, normalize_asset_path
from .neo4j_client import Neo4jGraphClient
import json
import os
import logging
from typing import Dict, Any, List, Optional

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

    def _generate_id(
        self,
        entity_type: str,
        *parts: str,
        project_id: Optional[str] = None,
    ) -> str:
        """Create a URN-based identifier for graph nodes."""
        resolved_project = project_id or "default"
        asset_path = "/".join(str(part) for part in parts if part)
        normalized_path = normalize_asset_path(asset_path)
        return generate_urn(entity_type, resolved_project, normalized_path)

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
        # Inject default metadata for hybrid lineage system
        # These defaults apply to deterministic (parser-based) edges
        metadata = {
            "source": properties.get("source", "parser"),
            "confidence": properties.get("confidence", 1.0),
            "status": properties.get("status", "approved"),
        }
        # Merge with any additional properties
        merged_properties = {**metadata, **properties}

        rel_data = {
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            **merged_properties,
        }

        if self.enable_batching:
            self._relationship_batch.append(rel_data)
            # Auto-flush if batch size reached
            if len(self._relationship_batch) >= self.batch_size:
                self._flush_relationships()
        else:
            # Fallback to individual write
            self.client.add_relationship(
                source_id, target_id, relationship_type, **merged_properties
            )

    def ingest_lineage_result(
        self,
        result: LineageResult,
        *,
        project_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        source_file: Optional[str] = None,
        source: Optional[str] = None,
        source_repo: Optional[str] = None,
    ) -> int:
        """Ingest standardized lineage results into Neo4j."""
        common_properties: Dict[str, Any] = {
            "project_id": project_id,
            "repository_id": repository_id,
            "source_file": source_file,
        }
        if source:
            common_properties["source"] = source
        if source_repo:
            common_properties["source_repo"] = source_repo

        node_ids: Dict[tuple[str, str], str] = {}
        fallback_ids: Dict[str, str] = {}
        nodes_created = 0

        def register_node(
            label: str,
            name: str,
            subtype: Optional[str] = None,
            properties: Optional[Dict[str, Any]] = None,
        ) -> str:
            nonlocal nodes_created
            node_key = (label, name)
            if node_key in node_ids:
                return node_ids[node_key]

            merged = {**common_properties}
            merged.update(properties or {})
            merged.setdefault("name", name)
            if subtype:
                merged.setdefault("subtype", subtype)
            merged = {key: value for key, value in merged.items() if value is not None}

            entity_id = self._generate_id(label, name, project_id=project_id)
            self._add_entity_to_batch(
                entity_id=entity_id,
                entity_type=label,
                **merged,
            )
            node_ids[node_key] = entity_id
            fallback_ids.setdefault(name, entity_id)
            nodes_created += 1
            return entity_id

        for node in result.nodes:
            register_node(node.label, node.name, node.type, node.properties)

        for external in result.external_refs:
            register_node(
                "DataAsset",
                external,
                "Table",
                {"external_ref": True, "name": external},
            )

        for edge in result.edges:
            source_label = (
                edge.properties.get("source_label") if edge.properties else None
            )
            target_label = (
                edge.properties.get("target_label") if edge.properties else None
            )

            if source_label:
                source_id = node_ids.get((source_label, edge.source))
            else:
                source_id = fallback_ids.get(edge.source)
            if target_label:
                target_id = node_ids.get((target_label, edge.target))
            else:
                target_id = fallback_ids.get(edge.target)

            if not source_id:
                source_id = register_node(
                    "DataAsset",
                    edge.source,
                    "Table",
                    {"external_ref": True, "name": edge.source},
                )
            if not target_id:
                target_id = register_node(
                    "DataAsset",
                    edge.target,
                    "Table",
                    {"external_ref": True, "name": edge.target},
                )

            edge_properties = {
                key: value
                for key, value in (edge.properties or {}).items()
                if key not in {"source_label", "target_label"}
            }
            edge_properties.update(
                {
                    key: value
                    for key, value in common_properties.items()
                    if value is not None
                }
            )
            if source:
                edge_properties["source"] = source
            if source_repo:
                edge_properties["source_repo"] = source_repo
            self._add_relationship_to_batch(
                source_id,
                target_id,
                edge.relationship,
                **edge_properties,
            )

        enrichments = result.metadata.get("enrichments", []) if result.metadata else []
        for enrichment in enrichments:
            name = enrichment.get("name")
            properties = enrichment.get("properties", {})
            if not name or not properties:
                continue
            try:
                query = """
                MATCH (n)
                WHERE toLower(n.name) = toLower($name)
                   OR toLower(n.name) ENDS WITH toLower($name)
                SET n += $properties
                RETURN count(n) as updated
                """
                self.client._execute_query(
                    query,
                    {"name": name, "properties": properties},
                )
            except Exception as exc:
                logger.warning("Failed to apply enrichment for %s: %s", name, exc)

        return nodes_created

    def _flush_entities(self):
        """Flush accumulated entities to Neo4j using batch operations.

        Groups entities by entity_type to ensure homogeneous batches,
        as batch_create_entities uses the first entity's type for all.
        """
        if not self._entity_batch:
            return

        count = len(self._entity_batch)
        logger.debug(f"Flushing {count} entities to Neo4j")

        try:
            # Group entities by type to ensure homogeneous batches
            from collections import defaultdict

            by_type = defaultdict(list)
            for entity in self._entity_batch:
                entity_type = entity.get("entity_type", "Node")
                by_type[entity_type].append(entity)

            total_created = 0
            for entity_type, entities in by_type.items():
                logger.debug(f"Flushing {len(entities)} {entity_type} entities")
                created = self.client.batch_create_entities(
                    entities=entities, batch_size=self.batch_size
                )
                total_created += created

            logger.info(f"Successfully flushed {total_created}/{count} entities")
        except Exception as e:
            logger.error(f"Failed to flush entities: {e}")
            raise
        finally:
            # Clear batch regardless of success/failure
            self._entity_batch.clear()

    def _flush_relationships(self):
        """Flush accumulated relationships to Neo4j using batch operations.

        Groups relationships by relationship_type to ensure homogeneous batches,
        as batch_create_relationships uses the first relationship's type for all.
        """
        if not self._relationship_batch:
            return

        count = len(self._relationship_batch)
        logger.debug(f"Flushing {count} relationships to Neo4j")

        try:
            # Group relationships by type to ensure homogeneous batches
            from collections import defaultdict

            by_type = defaultdict(list)
            for rel in self._relationship_batch:
                rel_type = rel.get("relationship_type", "RELATED_TO")
                by_type[rel_type].append(rel)

            total_created = 0
            for rel_type, relationships in by_type.items():
                logger.debug(f"Flushing {len(relationships)} {rel_type} relationships")
                created = self.client.batch_create_relationships(
                    relationships=relationships, batch_size=self.batch_size
                )
                total_created += created

            logger.info(f"Successfully flushed {total_created}/{count} relationships")
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
        self,
        sql_content: str,
        dialect: str = "auto",
        source_file: str = "unknown",
        file_node_id: str = None,
        project_id: Optional[str] = None,
        repository_id: Optional[str] = None,
        source: Optional[str] = None,
        source_repo: Optional[str] = None,
    ):
        """
        Parses a SQL script and ingests the resulting lineage into Neo4j.
        This method orchestrates the parsing and graph creation process.

        Args:
            sql_content: The SQL script to process.
            dialect: The SQL dialect of the script.
            source_file: The name of the file this SQL came from.
            project_id: Optional project identifier for tagging nodes.
            repository_id: Optional repository identifier for tagging nodes.
            source: Optional ingestion source label (e.g., upload/github).
            source_repo: Optional source repository identifier (e.g., owner/repo).
        """
        parsed_data = self.parser.parse_sql(sql_content, dialect=dialect)

        if not parsed_data:
            print(f"Skipping ingestion for {source_file} as parsing yielded no data.")
            return 0

        nodes_created = 0
        common_properties: Dict[str, Any] = {
            "project_id": project_id,
            "repository_id": repository_id,
            "source_file": source_file,
        }
        if source:
            common_properties["source"] = source
        if source_repo:
            common_properties["source_repo"] = source_repo

        def add_entity(entity_id: str, entity_type: str, **properties: Any) -> None:
            nonlocal nodes_created
            merged = {**common_properties, **properties}
            merged = {key: value for key, value in merged.items() if value is not None}
            self._add_entity_to_batch(
                entity_id=entity_id,
                entity_type=entity_type,
                **merged,
            )
            nodes_created += 1

        # 1. Ingest Data Assets (Tables, Views)
        write_asset_id = None
        if parsed_data.get("write") and parsed_data["write"] != "console":
            write_asset_id = self._generate_id(
                "data_asset",
                parsed_data["write"],
                project_id=project_id,
            )
            asset_type = (
                "View"
                if parsed_data["write"] in parsed_data.get("views", [])
                else "Table"
            )
            add_entity(
                entity_id=write_asset_id,
                entity_type=asset_type,
                name=parsed_data["write"],
            )

        read_asset_ids = {}
        for asset_name in parsed_data.get("read", []):
            asset_id = self._generate_id(
                "data_asset",
                asset_name,
                project_id=project_id,
            )
            read_asset_ids[asset_name] = asset_id
            add_entity(
                entity_id=asset_id,
                entity_type="DataAsset",  # Generic type, could be table or view
                name=asset_name,
            )

        # Link Write Asset to Read Assets (Table/View/MV Lineage)
        if write_asset_id:
            # Determine relationship type (Target DEPENDS_ON Source)
            is_mv = parsed_data["write"] in parsed_data.get("materialized_views", [])
            is_view = parsed_data["write"] in parsed_data.get("views", [])

            rel_type = "DERIVES" if (is_mv or is_view) else "READS_FROM"

            for source_id in read_asset_ids.values():
                self._add_relationship_to_batch(write_asset_id, source_id, rel_type)

        # 2. Ingest Column-Level Lineage
        for col_lineage in parsed_data.get("columns", []):
            target_col_name = col_lineage["target"]

            # We need to associate the target column with the write asset
            if not write_asset_id:
                continue

            target_col_id = self._generate_id(
                "column",
                parsed_data["write"],
                target_col_name,
                project_id=project_id,
            )
            add_entity(
                entity_id=target_col_id, entity_type="Column", name=target_col_name
            )
            # Link column to its parent asset
            self._add_relationship_to_batch(write_asset_id, target_col_id, "CONTAINS")

            # Create transformation node
            transformation_logic = col_lineage["transformation"]
            trans_id = self._generate_id(
                "transformation",
                transformation_logic,
                target_col_id,
                project_id=project_id,
            )
            add_entity(
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
                    source_asset_id = self._generate_id(
                        "data_asset",
                        source_table_name,
                        project_id=project_id,
                    )
                    add_entity(
                        entity_id=source_asset_id,
                        entity_type="DataAsset",
                        name=source_table_name,
                    )
                    read_asset_ids[source_table_name] = source_asset_id

                source_col_id = self._generate_id(
                    "column",
                    source_table_name,
                    source_col_name,
                    project_id=project_id,
                )
                add_entity(
                    entity_id=source_col_id, entity_type="Column", name=source_col_name
                )
                self._add_relationship_to_batch(
                    source_asset_id, source_col_id, "CONTAINS"
                )
                self._add_relationship_to_batch(source_col_id, trans_id, "INPUT_TO")

        # 3. Ingest Functions and Procedures
        for func_name in parsed_data.get("functions_and_procedures", []):
            func_id = self._generate_id(
                "function",
                func_name,
                project_id=project_id,
            )
            add_entity(
                entity_id=func_id,
                entity_type="FunctionOrProcedure",
                name=func_name,
            )

        # 4. Ingest Triggers
        for trigger_data in parsed_data.get("triggers", []):
            trigger_name = trigger_data.get("name")
            target_table = trigger_data.get("target_table")

            trigger_id = self._generate_id(
                "trigger",
                trigger_name,
                project_id=project_id,
            )
            add_entity(
                entity_id=trigger_id,
                entity_type="Trigger",
                name=trigger_name,
            )

            if target_table:
                target_id = self._generate_id(
                    "data_asset",
                    target_table,
                    project_id=project_id,
                )
                # Ensure target node exists (might differ from general read/write assets)
                add_entity(
                    entity_id=target_id, entity_type="DataAsset", name=target_table
                )
                self._add_relationship_to_batch(trigger_id, target_id, "ATTACHED_TO")

        # 5. Ingest Synonyms
        for synonym_data in parsed_data.get("synonyms", []):
            synonym_name = synonym_data.get("name")
            target_obj = synonym_data.get("target_object")

            synonym_id = self._generate_id(
                "synonym",
                synonym_name,
                project_id=project_id,
            )
            add_entity(
                entity_id=synonym_id,
                entity_type="Synonym",
                name=synonym_name,
            )

            if target_obj:
                target_id = self._generate_id(
                    "data_asset",
                    target_obj,
                    project_id=project_id,
                )
                add_entity(
                    entity_id=target_id, entity_type="DataAsset", name=target_obj
                )
                self._add_relationship_to_batch(synonym_id, target_id, "ALIAS_OF")

        # 6. Ingest Materialized Views
        for mv_name in parsed_data.get("materialized_views", []):
            mv_id = self._generate_id(
                "materialized_view",
                mv_name,
                project_id=project_id,
            )
            add_entity(
                entity_id=mv_id,
                entity_type="MaterializedView",
                name=mv_name,
            )

        # 7. Ingest Procedure Calls
        for proc_call in parsed_data.get("procedure_calls", []):
            proc_name = proc_call.get("name")
            if not proc_name:
                continue

            # Create or reference the procedure being called
            called_proc_id = self._generate_id(
                "procedure",
                proc_name,
                project_id=project_id,
            )
            add_entity(
                entity_id=called_proc_id,
                entity_type="FunctionOrProcedure",
                name=proc_name,
            )

            # Link call
            # If the SQL defines a procedure, assume it makes the call
            is_proc_def = write_asset_id and parsed_data["write"] in parsed_data.get(
                "functions_and_procedures", []
            )
            call_source = write_asset_id if is_proc_def else file_node_id

            if call_source:
                self._add_relationship_to_batch(call_source, called_proc_id, "CALLS")

        print(f"Successfully ingested lineage from {source_file}.")
        return nodes_created

    def ingest_file(self, file_path: str, project_id: Optional[str] = None):
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
        file_id = self._generate_id(
            "file",
            file_path,
            project_id=project_id,
        )
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
                self.ingest_sql_lineage(
                    content,
                    source_file=filename,
                    file_node_id=file_id,
                    project_id=project_id,
                )

            elif ext == ".py":
                print(f"[*] Ingesting Python: {filename}")
                self.ingest_python(
                    content,
                    source_file=filename,
                    file_node_id=file_id,
                    project_id=project_id,
                )

            elif ext == ".json":
                print(f"[*] Ingesting JSON: {filename}")
                self.ingest_json(
                    content,
                    source_file=filename,
                    file_node_id=file_id,
                    project_id=project_id,
                )

            else:
                print(f"[i] Skipping unsupported file type: {ext}")

        except Exception as e:
            print(f"[!] Error processing {file_path}: {e}")

    def ingest_python(
        self,
        content: str,
        source_file: str,
        file_node_id: str = None,
        project_id: Optional[str] = None,
    ):
        """Ingest Python structure."""
        parsed = self.parser.parse_python(content)
        if not parsed:
            return

        # Ingest Classes
        for cls in parsed["classes"]:
            cls_id = self._generate_id(
                "class",
                cls["name"],
                source_file,
                project_id=project_id,
            )
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
            func_id = self._generate_id(
                "function",
                func["name"],
                source_file,
                project_id=project_id,
            )
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
            mod_id = self._generate_id(
                "module",
                imp,
                project_id=project_id,
            )
            self._add_entity_to_batch(entity_id=mod_id, entity_type="Module", name=imp)
            if file_node_id:
                self._add_relationship_to_batch(file_node_id, mod_id, "IMPORTS")

        # Ingest Heuristic Table References (Python -> SQL lineage)
        for table_ref in parsed.get("table_references", []):
            table_id = self._generate_id(
                "data_asset",
                table_ref,
                project_id=project_id,
            )
            self._add_entity_to_batch(
                entity_id=table_id,
                entity_type="DataAsset",
                name=table_ref,
            )
            # Create READS_FROM edge from file to table (heuristic)
            if file_node_id:
                self._add_relationship_to_batch(
                    file_node_id,
                    table_id,
                    "READS_FROM",
                    evidence=f"Heuristic extraction from Python code in {source_file}",
                )

    def ingest_json(
        self,
        content: str,
        source_file: str,
        file_node_id: str = None,
        project_id: Optional[str] = None,
    ):
        """Ingest JSON structure."""
        parsed = self.parser.parse_json(content)
        if not parsed:
            return

        json_id = self._generate_id(
            "json_doc",
            source_file,
            project_id=project_id,
        )
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
            key_id = self._generate_id(
                "json_key",
                source_file,
                key,
                project_id=project_id,
            )
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
