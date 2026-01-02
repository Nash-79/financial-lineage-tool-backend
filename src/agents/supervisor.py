"""
Supervisor Agent for Multi-Agent Lineage System.

The supervisor agent orchestrates multiple specialized agents to answer
lineage queries. It uses Azure AI Foundry for agent management and GPT-4o
for reasoning and planning.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import asyncio

from openai import AzureOpenAI


class AgentRole(str, Enum):
    """Roles of specialized agents."""

    SQL_CORPUS = "sql_corpus_agent"
    KNOWLEDGE_GRAPH = "knowledge_graph_agent"
    VALIDATION = "validation_agent"


@dataclass
class AgentMessage:
    """Message passed between agents."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    agent: Optional[AgentRole] = None
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)


@dataclass
class LineageQuery:
    """Structured lineage query."""

    original_question: str
    target_entity: Optional[str] = None
    source_entity: Optional[str] = None
    query_type: str = (
        "general"  # column_lineage, table_lineage, transformation, validation
    )
    filters: dict = field(default_factory=dict)


@dataclass
class LineageResult:
    """Structured lineage result."""

    query: LineageQuery
    lineage_paths: list[dict] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    validation_issues: list[dict] = field(default_factory=list)
    narrative: str = ""
    confidence_score: float = 0.0
    sources_used: list[str] = field(default_factory=list)


class Tool:
    """Represents a tool that agents can use."""

    def __init__(
        self, name: str, description: str, parameters: dict, function: Callable
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.function = function

    def to_openai_tool(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs) -> Any:
        """Execute the tool."""
        if asyncio.iscoroutinefunction(self.function):
            return await self.function(**kwargs)
        return self.function(**kwargs)


class SupervisorAgent:
    """
    Supervisor agent that orchestrates the multi-agent lineage system.

    Responsibilities:
    - Parse and understand user queries
    - Decompose complex queries into sub-tasks
    - Route tasks to appropriate specialist agents
    - Aggregate and validate results
    - Generate coherent responses
    """

    SYSTEM_PROMPT = """You are a Financial Data Lineage Supervisor Agent. Your role is to orchestrate 
specialized agents to answer questions about data lineage in financial systems.

You have access to three specialist agents:
1. SQL Corpus Agent (/srchagent): Searches and analyzes SQL code to find column transformations, 
   table relationships, and data flows. Use for questions about SQL logic, transformations, joins.

2. Knowledge Graph Agent (/kbagent): Queries the lineage knowledge graph in Cosmos DB to find 
   established relationships between entities. Use for upstream/downstream lineage traversal.

3. Validation Agent (/valagent): Validates lineage paths for data type compatibility, 
   transformation correctness, and identifies potential issues. Use to verify lineage accuracy.

Your workflow:
1. Analyze the user's question to understand what lineage information they need
2. Determine which agents to invoke and in what order
3. Synthesize results from multiple agents into a coherent answer
4. Include confidence scores and note any uncertainties

For lineage queries, always try to provide:
- The complete path from source to target
- Any transformations applied along the way
- Data type changes
- Validation of the lineage accuracy

When you need to call an agent, use the appropriate tool. After getting results, 
synthesize them into a clear, structured response."""

    def __init__(
        self,
        openai_client: AzureOpenAI,
        deployment_name: str = "gpt-4o",
        sql_agent: Optional["SQLCorpusAgent"] = None,
        kg_agent: Optional["KnowledgeGraphAgent"] = None,
        validation_agent: Optional["ValidationAgent"] = None,
        max_iterations: int = 10,
    ):
        """
        Initialize the supervisor agent.

        Args:
            openai_client: Azure OpenAI client
            deployment_name: GPT-4o deployment name
            sql_agent: SQL corpus agent instance
            kg_agent: Knowledge graph agent instance
            validation_agent: Validation agent instance
            max_iterations: Maximum agent iterations
        """
        self.client = openai_client
        self.deployment = deployment_name
        self.sql_agent = sql_agent
        self.kg_agent = kg_agent
        self.validation_agent = validation_agent
        self.max_iterations = max_iterations

        # Build tools from agents
        self.tools = self._build_tools()

    def _build_tools(self) -> list[Tool]:
        """Build tool definitions from available agents."""
        tools = []

        # SQL Corpus Agent tool
        tools.append(
            Tool(
                name="query_sql_corpus",
                description="""Search the SQL code corpus to find relevant code chunks. 
            Use this to find SQL statements that define, transform, or reference specific 
            tables and columns. Returns matching SQL code with metadata.""",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query about SQL code to find",
                        },
                        "table_filter": {
                            "type": "string",
                            "description": "Optional: filter by table name",
                        },
                        "column_filter": {
                            "type": "string",
                            "description": "Optional: filter by column name",
                        },
                        "search_type": {
                            "type": "string",
                            "enum": [
                                "transformation",
                                "definition",
                                "join",
                                "aggregation",
                            ],
                            "description": "Type of SQL pattern to search for",
                        },
                    },
                    "required": ["query"],
                },
                function=self._call_sql_agent,
            )
        )

        # Knowledge Graph Agent tool
        tools.append(
            Tool(
                name="query_knowledge_graph",
                description="""Query the lineage knowledge graph to find relationships between 
            data entities. Use this for traversing upstream/downstream lineage, finding 
            all sources of a column, or discovering dependencies.""",
                parameters={
                    "type": "object",
                    "properties": {
                        "entity_name": {
                            "type": "string",
                            "description": "Name of the entity (table.column or table)",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["upstream", "downstream", "both"],
                            "description": "Direction to traverse lineage",
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum traversal depth",
                            "default": 5,
                        },
                        "include_transformations": {
                            "type": "boolean",
                            "description": "Whether to include transformation details",
                            "default": True,
                        },
                    },
                    "required": ["entity_name", "direction"],
                },
                function=self._call_kg_agent,
            )
        )

        # Validation Agent tool
        tools.append(
            Tool(
                name="validate_lineage",
                description="""Validate a lineage path for correctness and compatibility.
            Checks data type compatibility, transformation logic validity, and identifies
            potential issues or breaking changes.""",
                parameters={
                    "type": "object",
                    "properties": {
                        "source_entity": {
                            "type": "string",
                            "description": "Source entity in the lineage path",
                        },
                        "target_entity": {
                            "type": "string",
                            "description": "Target entity in the lineage path",
                        },
                        "lineage_path": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "The lineage path to validate",
                        },
                        "validation_type": {
                            "type": "string",
                            "enum": [
                                "data_types",
                                "transformations",
                                "completeness",
                                "all",
                            ],
                            "description": "Type of validation to perform",
                        },
                    },
                    "required": ["source_entity", "target_entity"],
                },
                function=self._call_validation_agent,
            )
        )

        return tools

    async def _call_sql_agent(
        self,
        query: str,
        table_filter: Optional[str] = None,
        column_filter: Optional[str] = None,
        search_type: Optional[str] = None,
    ) -> dict:
        """Call the SQL corpus agent."""
        if self.sql_agent is None:
            return {"error": "SQL corpus agent not available"}

        return await self.sql_agent.search(
            query=query,
            table_filter=table_filter,
            column_filter=column_filter,
            search_type=search_type,
        )

    async def _call_kg_agent(
        self,
        entity_name: str,
        direction: str,
        max_depth: int = 5,
        include_transformations: bool = True,
    ) -> dict:
        """Call the knowledge graph agent."""
        if self.kg_agent is None:
            return {"error": "Knowledge graph agent not available"}

        return await self.kg_agent.query_lineage(
            entity_name=entity_name,
            direction=direction,
            max_depth=max_depth,
            include_transformations=include_transformations,
        )

    async def _call_validation_agent(
        self,
        source_entity: str,
        target_entity: str,
        lineage_path: Optional[list] = None,
        validation_type: str = "all",
    ) -> dict:
        """Call the validation agent."""
        if self.validation_agent is None:
            return {"error": "Validation agent not available"}

        return await self.validation_agent.validate(
            source_entity=source_entity,
            target_entity=target_entity,
            lineage_path=lineage_path,
            validation_type=validation_type,
        )

    async def process_query(self, user_query: str) -> LineageResult:
        """
        Process a user query through the multi-agent system.

        Args:
            user_query: Natural language query about data lineage

        Returns:
            Structured lineage result with paths, transformations, and validation
        """
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ]

        iteration = 0
        collected_results = {
            "sql_results": [],
            "kg_results": [],
            "validation_results": [],
        }

        while iteration < self.max_iterations:
            # Call the model
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                tools=[t.to_openai_tool() for t in self.tools],
                tool_choice="auto",
                temperature=0.1,
            )

            assistant_message = response.choices[0].message
            messages.append(assistant_message.model_dump())

            # Check if we're done (no tool calls)
            if not assistant_message.tool_calls:
                break

            # Process tool calls
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                # Find and execute the tool
                tool_result = None
                for tool in self.tools:
                    if tool.name == function_name:
                        tool_result = await tool.execute(**arguments)
                        break

                if tool_result is None:
                    tool_result = {"error": f"Unknown tool: {function_name}"}

                # Store results by type
                if "sql" in function_name:
                    collected_results["sql_results"].append(tool_result)
                elif "knowledge_graph" in function_name:
                    collected_results["kg_results"].append(tool_result)
                elif "validate" in function_name:
                    collected_results["validation_results"].append(tool_result)

                # Add tool result to messages
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str),
                    }
                )

            iteration += 1

        # Extract final response
        final_response = messages[-1].get("content", "") if messages else ""
        if hasattr(messages[-1], "content"):
            final_response = messages[-1].content or ""

        # Build structured result
        return self._build_result(
            query=LineageQuery(original_question=user_query),
            collected_results=collected_results,
            narrative=final_response,
        )

    def _build_result(
        self, query: LineageQuery, collected_results: dict, narrative: str
    ) -> LineageResult:
        """Build a structured result from collected agent outputs."""
        lineage_paths = []
        transformations = []
        validation_issues = []
        sources_used = []

        # Extract lineage paths from KG results
        for kg_result in collected_results.get("kg_results", []):
            if isinstance(kg_result, dict):
                if "paths" in kg_result:
                    lineage_paths.extend(kg_result["paths"])
                if "upstream" in kg_result:
                    lineage_paths.extend(kg_result.get("upstream", []))
                if "downstream" in kg_result:
                    lineage_paths.extend(kg_result.get("downstream", []))

        # Extract transformations from SQL results
        for sql_result in collected_results.get("sql_results", []):
            if isinstance(sql_result, dict):
                if "transformations" in sql_result:
                    transformations.extend(sql_result["transformations"])
                if "results" in sql_result:
                    for r in sql_result["results"]:
                        sources_used.append(r.get("file_path", ""))

        # Extract validation issues
        for val_result in collected_results.get("validation_results", []):
            if isinstance(val_result, dict):
                if "issues" in val_result:
                    validation_issues.extend(val_result["issues"])

        # Calculate confidence
        confidence = 1.0
        if validation_issues:
            confidence -= 0.1 * len(validation_issues)
        if not lineage_paths:
            confidence -= 0.3
        confidence = max(0.0, confidence)

        return LineageResult(
            query=query,
            lineage_paths=lineage_paths,
            transformations=transformations,
            validation_issues=validation_issues,
            narrative=narrative,
            confidence_score=confidence,
            sources_used=list(set(sources_used)),
        )


class SQLCorpusAgent:
    """
    Agent specialized in searching and analyzing SQL code corpus.

    Grounded on: Azure AI Search (SQL code index)
    """

    SYSTEM_PROMPT = """You are a SQL Corpus Analysis Agent. Your role is to search and analyze 
SQL code to extract lineage information.

When analyzing SQL:
1. Identify source tables (FROM, JOIN)
2. Identify target tables (INSERT INTO, CREATE TABLE AS)
3. Extract column transformations (SELECT expressions)
4. Note data type changes (CAST, CONVERT)
5. Identify aggregations (GROUP BY, SUM, AVG, etc.)
6. Find filter conditions that affect data flow

Return structured information about the SQL patterns found."""

    def __init__(
        self,
        openai_client: AzureOpenAI,
        search_client: "CodeSearchIndex",
        deployment_name: str = "gpt-4o",
    ):
        self.client = openai_client
        self.search = search_client
        self.deployment = deployment_name

    async def search(
        self,
        query: str,
        table_filter: Optional[str] = None,
        column_filter: Optional[str] = None,
        search_type: Optional[str] = None,
    ) -> dict:
        """Search the SQL corpus and analyze results."""
        # Search the corpus
        tables_filter = [table_filter] if table_filter else None
        search_results = self.search.hybrid_search(
            query=query, language="sql", tables=tables_filter, top_k=10
        )

        if not search_results:
            return {
                "results": [],
                "transformations": [],
                "message": "No matching SQL code found",
            }

        # Analyze results with GPT-4o
        analysis_prompt = f"""Analyze these SQL code chunks to extract lineage information.

Query: {query}
{f'Focus on table: {table_filter}' if table_filter else ''}
{f'Focus on column: {column_filter}' if column_filter else ''}

SQL Code Chunks:
"""
        for i, result in enumerate(search_results[:5]):
            analysis_prompt += f"\n--- Chunk {i+1} (from {result.file_path}) ---\n"
            analysis_prompt += result.content[:2000]  # Truncate long chunks

        analysis_prompt += """

Extract and return as JSON:
{
    "transformations": [{"source": "...", "target": "...", "logic": "..."}],
    "tables_involved": ["..."],
    "columns_mapped": [{"source_col": "...", "target_col": "...", "transformation": "..."}],
    "data_types": [{"column": "...", "from_type": "...", "to_type": "..."}]
}"""

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": analysis_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        try:
            analysis = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            analysis = {"error": "Failed to parse analysis"}

        return {
            "results": [
                {
                    "content": r.content[:500],
                    "file_path": r.file_path,
                    "score": r.score,
                    "tables": r.tables_referenced,
                }
                for r in search_results[:5]
            ],
            "transformations": analysis.get("transformations", []),
            "columns_mapped": analysis.get("columns_mapped", []),
            "data_types": analysis.get("data_types", []),
        }


class KnowledgeGraphAgent:
    """
    Agent specialized in querying the lineage knowledge graph.

    Grounded on: Cosmos DB Gremlin API
    """

    def __init__(
        self,
        openai_client: AzureOpenAI,
        cosmos_client: "CosmosGremlinClient",
        deployment_name: str = "gpt-4o",
    ):
        self.client = openai_client
        self.cosmos = cosmos_client
        self.deployment = deployment_name

    async def query_lineage(
        self,
        entity_name: str,
        direction: str,
        max_depth: int = 5,
        include_transformations: bool = True,
    ) -> dict:
        """Query lineage from the knowledge graph."""
        # Parse entity name (table.column or just table)
        parts = entity_name.split(".")

        # Find the entity
        entities = self.cosmos.find_entities_by_name(parts[-1])

        if not entities:
            return {
                "entity": entity_name,
                "error": "Entity not found in knowledge graph",
            }

        entity = entities[0]

        # Get lineage based on direction
        result = {
            "entity": entity_name,
            "entity_id": entity.id,
            "upstream": [],
            "downstream": [],
            "paths": [],
        }

        if direction in ["upstream", "both"]:
            upstream = self.cosmos.get_upstream_lineage(entity.id, max_depth)
            result["upstream"] = self._format_lineage_paths(upstream)

        if direction in ["downstream", "both"]:
            downstream = self.cosmos.get_downstream_lineage(entity.id, max_depth)
            result["downstream"] = self._format_lineage_paths(downstream)

        if include_transformations:
            transformations = self.cosmos.get_transformation_summary(entity.id)
            result["transformations"] = transformations.get("transformations", [])

        return result

    def _format_lineage_paths(self, raw_paths: list) -> list[dict]:
        """Format raw graph paths into structured format."""
        formatted = []
        for path in raw_paths:
            if isinstance(path, list):
                formatted.append(
                    {
                        "nodes": [
                            {
                                "name": (
                                    node.get("name", [""])[0]
                                    if isinstance(node.get("name"), list)
                                    else node.get("name", "")
                                ),
                                "type": (
                                    node.get("entity_type", [""])[0]
                                    if isinstance(node.get("entity_type"), list)
                                    else node.get("entity_type", "")
                                ),
                            }
                            for node in path
                            if isinstance(node, dict)
                        ]
                    }
                )
        return formatted


class ValidationAgent:
    """
    Agent specialized in validating lineage paths.

    Grounded on: Source schemas and data types
    """

    def __init__(self, openai_client: AzureOpenAI, deployment_name: str = "gpt-4o"):
        self.client = openai_client
        self.deployment = deployment_name

    async def validate(
        self,
        source_entity: str,
        target_entity: str,
        lineage_path: Optional[list] = None,
        validation_type: str = "all",
    ) -> dict:
        """Validate a lineage path."""
        issues = []

        # Data type validation
        if validation_type in ["data_types", "all"]:
            type_issues = self._validate_data_types(lineage_path)
            issues.extend(type_issues)

        # Transformation validation
        if validation_type in ["transformations", "all"]:
            transform_issues = self._validate_transformations(lineage_path)
            issues.extend(transform_issues)

        # Completeness validation
        if validation_type in ["completeness", "all"]:
            completeness_issues = self._validate_completeness(
                source_entity, target_entity, lineage_path
            )
            issues.extend(completeness_issues)

        return {
            "source": source_entity,
            "target": target_entity,
            "is_valid": len(issues) == 0,
            "issues": issues,
            "validation_types_checked": (
                [validation_type]
                if validation_type != "all"
                else ["data_types", "transformations", "completeness"]
            ),
        }

    def _validate_data_types(self, lineage_path: Optional[list]) -> list[dict]:
        """Validate data type compatibility along the path."""
        issues = []
        if not lineage_path:
            return issues

        # Check for type mismatches
        for i, step in enumerate(lineage_path[:-1]):
            if isinstance(step, dict) and isinstance(lineage_path[i + 1], dict):
                source_type = step.get("data_type")
                target_type = lineage_path[i + 1].get("data_type")

                if source_type and target_type:
                    if not self._types_compatible(source_type, target_type):
                        issues.append(
                            {
                                "type": "data_type_mismatch",
                                "severity": "warning",
                                "message": f"Type change from {source_type} to {target_type}",
                                "location": f"Step {i + 1}",
                            }
                        )

        return issues

    def _types_compatible(self, source_type: str, target_type: str) -> bool:
        """Check if two data types are compatible."""
        # Simplified compatibility check
        numeric_types = {
            "int",
            "integer",
            "bigint",
            "decimal",
            "float",
            "double",
            "numeric",
        }
        string_types = {"varchar", "nvarchar", "char", "text", "string"}

        source_lower = source_type.lower().split("(")[0]
        target_lower = target_type.lower().split("(")[0]

        if source_lower == target_lower:
            return True
        if source_lower in numeric_types and target_lower in numeric_types:
            return True
        if source_lower in string_types and target_lower in string_types:
            return True

        return False

    def _validate_transformations(self, lineage_path: Optional[list]) -> list[dict]:
        """Validate transformation logic."""
        issues = []
        # Add transformation validation logic
        return issues

    def _validate_completeness(
        self, source: str, target: str, lineage_path: Optional[list]
    ) -> list[dict]:
        """Validate lineage completeness."""
        issues = []

        if not lineage_path:
            issues.append(
                {
                    "type": "incomplete_lineage",
                    "severity": "error",
                    "message": f"No lineage path found from {source} to {target}",
                }
            )

        return issues
