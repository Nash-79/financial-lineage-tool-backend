"""
Azure AI Search Integration for Code Lineage.

This module provides hybrid search capabilities (vector + keyword) for
finding relevant code chunks in the lineage corpus.
"""

from dataclasses import dataclass, field
from typing import Optional

from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI


@dataclass
class SearchResult:
    """Represents a search result from the code corpus."""

    id: str
    content: str
    score: float
    language: str
    file_path: str
    repo_name: str
    chunk_type: str
    tables_referenced: list[str] = field(default_factory=list)
    columns_referenced: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)


class CodeSearchIndex:
    """
    Manages the Azure AI Search index for code lineage corpus.

    Features:
    - Hybrid search (vector + keyword)
    - Semantic ranking
    - Filtering by language, repo, chunk type
    - Table/column reference filtering
    """

    INDEX_NAME = "code-lineage-index"
    VECTOR_DIMENSIONS = 1536  # text-embedding-ada-002

    def __init__(
        self,
        search_endpoint: str,
        search_key: str,
        openai_endpoint: str,
        openai_key: str,
        embedding_deployment: str = "text-embedding-ada-002",
    ):
        """
        Initialize the search index manager.

        Args:
            search_endpoint: Azure AI Search endpoint
            search_key: Azure AI Search admin key
            openai_endpoint: Azure OpenAI endpoint
            openai_key: Azure OpenAI key
            embedding_deployment: Embedding model deployment name
        """
        self.search_endpoint = search_endpoint
        self.search_credential = AzureKeyCredential(search_key)

        self.index_client = SearchIndexClient(
            endpoint=search_endpoint, credential=self.search_credential
        )

        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=self.INDEX_NAME,
            credential=self.search_credential,
        )

        self.openai_client = AzureOpenAI(
            azure_endpoint=openai_endpoint, api_key=openai_key, api_version="2024-02-01"
        )
        self.embedding_deployment = embedding_deployment

    def create_index(self) -> None:
        """Create or update the search index with the lineage schema."""
        fields = [
            SimpleField(
                name="id", type=SearchFieldDataType.String, key=True, filterable=True
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
                analyzer_name="standard.lucene",
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.VECTOR_DIMENSIONS,
                vector_search_profile_name="vector-profile",
            ),
            SearchableField(
                name="file_path",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="language",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="repo_name",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(
                name="chunk_type",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="tables_referenced",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
                facetable=True,
            ),
            SearchField(
                name="columns_referenced",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
            ),
            SearchableField(
                name="entities",
                type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                filterable=True,
            ),
            SimpleField(name="start_line", type=SearchFieldDataType.Int32),
            SimpleField(name="end_line", type=SearchFieldDataType.Int32),
            SimpleField(name="token_count", type=SearchFieldDataType.Int32),
            SearchableField(name="context_prefix", type=SearchFieldDataType.String),
        ]

        # Vector search configuration
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw-config",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine",
                    },
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile", algorithm_configuration_name="hnsw-config"
                )
            ],
        )

        # Semantic configuration
        semantic_config = SemanticConfiguration(
            name="lineage-semantic",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[
                    SemanticField(field_name="tables_referenced"),
                    SemanticField(field_name="columns_referenced"),
                ],
            ),
        )

        semantic_search = SemanticSearch(configurations=[semantic_config])

        index = SearchIndex(
            name=self.INDEX_NAME,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )

        self.index_client.create_or_update_index(index)

    def _generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using Azure OpenAI."""
        response = self.openai_client.embeddings.create(
            input=text, model=self.embedding_deployment
        )
        return response.data[0].embedding

    def index_document(self, document: dict) -> None:
        """
        Index a single document (code chunk).

        Args:
            document: Document to index with required fields
        """
        # Generate embedding for the content
        embedding_text = document.get("content", "")
        if document.get("context_prefix"):
            embedding_text = f"{document['context_prefix']}\n{embedding_text}"

        document["content_vector"] = self._generate_embedding(embedding_text)

        self.search_client.upload_documents([document])

    def index_documents_batch(
        self, documents: list[dict], batch_size: int = 100
    ) -> None:
        """
        Index multiple documents in batches.

        Args:
            documents: List of documents to index
            batch_size: Number of documents per batch
        """
        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            # Generate embeddings for batch
            for doc in batch:
                embedding_text = doc.get("content", "")
                if doc.get("context_prefix"):
                    embedding_text = f"{doc['context_prefix']}\n{embedding_text}"
                doc["content_vector"] = self._generate_embedding(embedding_text)

            self.search_client.upload_documents(batch)

    def hybrid_search(
        self,
        query: str,
        language: Optional[str] = None,
        repo_name: Optional[str] = None,
        chunk_types: Optional[list[str]] = None,
        tables: Optional[list[str]] = None,
        top_k: int = 10,
        use_semantic_ranking: bool = True,
    ) -> list[SearchResult]:
        """
        Perform hybrid search (vector + keyword) with optional filters.

        Args:
            query: Search query text
            language: Filter by language (sql, python, etc.)
            repo_name: Filter by repository name
            chunk_types: Filter by chunk types
            tables: Filter by tables referenced
            top_k: Number of results to return
            use_semantic_ranking: Whether to use semantic reranking

        Returns:
            List of search results
        """
        # Generate query embedding
        query_vector = self._generate_embedding(query)

        # Build filter expression
        filters = []
        if language:
            filters.append(f"language eq '{language}'")
        if repo_name:
            filters.append(f"repo_name eq '{repo_name}'")
        if chunk_types:
            chunk_filter = " or ".join(f"chunk_type eq '{ct}'" for ct in chunk_types)
            filters.append(f"({chunk_filter})")
        if tables:
            table_filters = " or ".join(
                f"tables_referenced/any(t: t eq '{table}')" for table in tables
            )
            filters.append(f"({table_filters})")

        filter_expression = " and ".join(filters) if filters else None

        # Create vector query
        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top_k * 2,  # Over-fetch for reranking
            fields="content_vector",
        )

        # Execute search
        search_params = {
            "search_text": query,
            "vector_queries": [vector_query],
            "top": top_k,
            "select": [
                "id",
                "content",
                "language",
                "file_path",
                "repo_name",
                "chunk_type",
                "tables_referenced",
                "columns_referenced",
                "start_line",
                "end_line",
            ],
            "highlight_fields": "content",
        }

        if filter_expression:
            search_params["filter"] = filter_expression

        if use_semantic_ranking:
            search_params["query_type"] = "semantic"
            search_params["semantic_configuration_name"] = "lineage-semantic"

        results = self.search_client.search(**search_params)

        search_results = []
        for result in results:
            search_results.append(
                SearchResult(
                    id=result["id"],
                    content=result["content"],
                    score=result["@search.score"],
                    language=result["language"],
                    file_path=result["file_path"],
                    repo_name=result["repo_name"],
                    chunk_type=result["chunk_type"],
                    tables_referenced=result.get("tables_referenced", []),
                    columns_referenced=result.get("columns_referenced", []),
                    highlights=result.get("@search.highlights", {}).get("content", []),
                )
            )

        return search_results

    def search_by_table(
        self, table_name: str, include_columns: bool = True, top_k: int = 20
    ) -> list[SearchResult]:
        """
        Find all code chunks that reference a specific table.

        Args:
            table_name: Table name to search for
            include_columns: Whether to also search column references
            top_k: Number of results

        Returns:
            Code chunks referencing the table
        """
        # Construct query to find table references
        query = f"table {table_name}"

        filter_expr = f"tables_referenced/any(t: search.in(t, '{table_name}', ','))"

        results = self.search_client.search(
            search_text=query,
            filter=filter_expr,
            top=top_k,
            select=[
                "id",
                "content",
                "language",
                "file_path",
                "repo_name",
                "chunk_type",
                "tables_referenced",
                "columns_referenced",
            ],
        )

        return [
            SearchResult(
                id=r["id"],
                content=r["content"],
                score=r["@search.score"],
                language=r["language"],
                file_path=r["file_path"],
                repo_name=r["repo_name"],
                chunk_type=r["chunk_type"],
                tables_referenced=r.get("tables_referenced", []),
                columns_referenced=r.get("columns_referenced", []),
            )
            for r in results
        ]

    def search_sql_transformations(
        self,
        column_name: str,
        transformation_type: Optional[str] = None,
        top_k: int = 10,
    ) -> list[SearchResult]:
        """
        Search for SQL code that transforms a specific column.

        Args:
            column_name: Column name to find transformations for
            transformation_type: Optional filter (CAST, CASE, JOIN, etc.)
            top_k: Number of results

        Returns:
            SQL chunks with transformations
        """
        query = f"{column_name}"
        if transformation_type:
            query += f" {transformation_type}"

        return self.hybrid_search(
            query=query,
            language="sql",
            chunk_types=["sql_cte", "sql_statement", "sql_subquery"],
            top_k=top_k,
        )

    def get_lineage_context(
        self, source_table: str, target_table: str, top_k: int = 10
    ) -> list[SearchResult]:
        """
        Find code that connects source to target table.

        Args:
            source_table: Source table name
            target_table: Target table name
            top_k: Number of results

        Returns:
            Code chunks showing the connection
        """
        query = f"SELECT FROM {source_table} INSERT INTO {target_table}"

        # Search for code that references both tables
        results = self.hybrid_search(
            query=query, tables=[source_table, target_table], top_k=top_k * 2
        )

        # Filter to keep only results mentioning both tables
        filtered = []
        for r in results:
            refs = set(r.tables_referenced)
            if source_table.lower() in [
                t.lower() for t in refs
            ] and target_table.lower() in [t.lower() for t in refs]:
                filtered.append(r)
            elif len(filtered) < top_k:
                # Include partial matches if not enough full matches
                filtered.append(r)

        return filtered[:top_k]


class SQLCorpusSearcher:
    """
    Specialized searcher for SQL corpus with lineage-aware queries.
    """

    def __init__(self, search_index: CodeSearchIndex):
        self.search_index = search_index

    def find_column_definitions(self, column_name: str) -> list[SearchResult]:
        """Find where a column is defined or aliased."""
        query = f"AS {column_name} SELECT {column_name}"
        return self.search_index.hybrid_search(query=query, language="sql", top_k=10)

    def find_joins_involving_table(self, table_name: str) -> list[SearchResult]:
        """Find JOIN clauses involving a table."""
        query = f"JOIN {table_name} ON"
        return self.search_index.hybrid_search(
            query=query, language="sql", tables=[table_name], top_k=15
        )

    def find_aggregations(self, column_name: str) -> list[SearchResult]:
        """Find aggregation operations on a column."""
        query = f"SUM AVG COUNT MAX MIN {column_name} GROUP BY"
        return self.search_index.hybrid_search(query=query, language="sql", top_k=10)

    def find_data_type_casts(self, column_name: str) -> list[SearchResult]:
        """Find CAST/CONVERT operations on a column."""
        query = f"CAST CONVERT {column_name} AS"
        return self.search_index.hybrid_search(query=query, language="sql", top_k=10)
