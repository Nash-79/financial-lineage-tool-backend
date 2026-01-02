"""
Configuration settings for the Financial Lineage Tool.
Uses pydantic-settings for environment variable management.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration."""
    
    model_config = SettingsConfigDict(env_prefix="AZURE_OPENAI_")
    
    endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    api_key: str = Field(..., description="Azure OpenAI API key")
    api_version: str = Field(default="2024-02-01", description="API version")
    deployment_gpt4o: str = Field(default="gpt-4o", description="GPT-4o deployment name")
    deployment_embedding: str = Field(
        default="text-embedding-ada-002", 
        description="Embedding model deployment name"
    )


class CosmosDBSettings(BaseSettings):
    """Cosmos DB Gremlin configuration."""
    
    model_config = SettingsConfigDict(env_prefix="COSMOS_")
    
    endpoint: str = Field(..., description="Cosmos DB Gremlin endpoint")
    key: str = Field(..., description="Cosmos DB primary key")
    database: str = Field(default="lineage-db", description="Database name")
    graph: str = Field(default="lineage-graph", description="Graph container name")
    

class AzureSearchSettings(BaseSettings):
    """Azure AI Search configuration."""
    
    model_config = SettingsConfigDict(env_prefix="SEARCH_")
    
    endpoint: str = Field(..., description="Azure AI Search endpoint")
    key: str = Field(..., description="Azure AI Search admin key")
    index_name: str = Field(default="code-lineage-index", description="Search index name")
    semantic_config: str = Field(default="lineage-semantic", description="Semantic configuration name")


class StorageSettings(BaseSettings):
    """Azure Blob Storage configuration."""
    
    model_config = SettingsConfigDict(env_prefix="STORAGE_")
    
    connection_string: str = Field(..., description="Storage connection string")
    container: str = Field(default="code-repos", description="Blob container name")


class GitHubSettings(BaseSettings):
    """GitHub configuration for repository ingestion."""
    
    model_config = SettingsConfigDict(env_prefix="GITHUB_")
    
    token: str = Field(..., description="GitHub personal access token")
    

class AgentSettings(BaseSettings):
    """Agent configuration."""
    
    model_config = SettingsConfigDict(env_prefix="AGENT_")
    
    max_iterations: int = Field(default=10, description="Max agent iterations")
    temperature: float = Field(default=0.1, description="LLM temperature for agents")
    max_tokens: int = Field(default=4096, description="Max tokens per response")
    timeout_seconds: int = Field(default=120, description="Agent timeout")


class ChunkingSettings(BaseSettings):
    """Semantic chunking configuration."""

    model_config = SettingsConfigDict(env_prefix="CHUNKING_")

    sql_max_tokens: int = Field(default=1500, description="Max tokens for SQL chunks")
    python_max_tokens: int = Field(default=1000, description="Max tokens for Python chunks")
    config_max_tokens: int = Field(default=500, description="Max tokens for config chunks")
    overlap_tokens: int = Field(default=100, description="Overlap tokens between chunks")


class DataPathSettings(BaseSettings):
    """Data folder path configuration."""

    model_config = SettingsConfigDict(env_prefix="DATA_")

    root: str = Field(default="./data", description="Root data directory")
    database_name: str = Field(default="default", description="Default database name for ingestion")


class DuckDBSettings(BaseSettings):
    """DuckDB metadata storage configuration."""

    model_config = SettingsConfigDict(env_prefix="DUCKDB_")

    path: str = Field(
        default="data/metadata.duckdb",
        description="DuckDB database path. Use ':memory:' for in-memory database (cloud hosting)."
    )


class UploadSettings(BaseSettings):
    """File upload configuration."""

    model_config = SettingsConfigDict(env_prefix="UPLOAD_")

    base_dir: str = Field(
        default="data/raw/uploaded",
        description="Base directory for uploaded files"
    )
    max_file_size_mb: int = Field(
        default=50,
        description="Maximum file size in MB"
    )
    allowed_extensions: list[str] = Field(
        default=[".sql", ".ddl", ".csv", ".json"],
        description="Allowed file extensions for upload"
    )


class GitHubOAuthSettings(BaseSettings):
    """GitHub OAuth configuration for repository integration."""

    model_config = SettingsConfigDict(env_prefix="GITHUB_")

    client_id: str = Field(default="", description="GitHub OAuth App client ID")
    client_secret: str = Field(default="", description="GitHub OAuth App client secret")
    redirect_uri: str = Field(
        default="http://localhost:5173/connectors/github/callback",
        description="OAuth callback redirect URI"
    )


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Application
    app_name: str = Field(default="Financial Lineage Tool", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Sub-configurations
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    cosmos: CosmosDBSettings = Field(default_factory=CosmosDBSettings)
    search: AzureSearchSettings = Field(default_factory=AzureSearchSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    github_oauth: GitHubOAuthSettings = Field(default_factory=GitHubOAuthSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    data_paths: DataPathSettings = Field(default_factory=DataPathSettings)
    duckdb: DuckDBSettings = Field(default_factory=DuckDBSettings)
    upload: UploadSettings = Field(default_factory=UploadSettings)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
