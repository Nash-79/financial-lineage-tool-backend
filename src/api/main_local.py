"""
Local Development API - Uses FREE alternatives to Azure services.

Replacements:
- Azure OpenAI → Ollama (local LLMs)
- Cosmos DB Gremlin → Neo4j (cloud graph database)
- Azure AI Search → Qdrant (local vector DB)
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ingestion.code_parser import CodeParser
from src.knowledge_graph.entity_extractor import GraphExtractor
from src.knowledge_graph.neo4j_client import Neo4jGraphClient
from src.services import LocalSupervisorAgent, OllamaClient, QdrantLocalClient, MemoryService, set_tracker_broadcast
from src.storage.duckdb_client import initialize_duckdb, close_duckdb
from src.storage.metadata_store import ensure_default_project

from .config import config
from .middleware import setup_activity_tracking, setup_cors, setup_error_handlers
from .routers import admin, chat, database, files, github, graph, health, ingest, lineage, metadata, projects


# ==================== Application State ====================


class AppState:
    """Global application state container."""

    ollama: Optional[OllamaClient] = None
    qdrant: Optional[QdrantLocalClient] = None
    graph: Optional[Neo4jGraphClient] = None
    agent: Optional[LocalSupervisorAgent] = None
    parser: Optional[CodeParser] = None
    extractor: Optional[GraphExtractor] = None
    llamaindex_service: Optional[Any] = None  # LlamaIndexService when enabled
    memory: Optional[MemoryService] = None  # Long-term chat memory
    redis_client: Optional[Any] = None  # Redis client for caching
    activity_tracker: Optional[Any] = None  # Activity tracking for metrics


state = AppState()


# ==================== Lifespan ====================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources.

    Handles startup and shutdown of all service connections including:
    - Ollama (LLM)
    - Qdrant (vector DB)
    - Neo4j (graph DB)
    - Redis (caching)
    - LlamaIndex (RAG framework)
    - Activity tracker

    Args:
        app: FastAPI application instance.

    Yields:
        None during application runtime.
    """
    print("[*] Starting Local Lineage Tool with Neo4j...")

    # Create data and log directories
    Path(config.STORAGE_PATH).mkdir(parents=True, exist_ok=True)
    Path(config.LOG_PATH).mkdir(parents=True, exist_ok=True)

    # Initialize DuckDB for metadata storage
    print(f"[*] Initializing DuckDB at {config.DUCKDB_PATH}...")
    try:
        initialize_duckdb(config.DUCKDB_PATH)
        print("[+] DuckDB initialized successfully")

        # Ensure default project exists for backward compatibility
        await ensure_default_project()
        print("[+] Default project ready")

        # Load upload settings from database
        print("[*] Loading upload settings from database...")
        from src.storage.upload_settings import UploadSettingsStore
        settings_store = UploadSettingsStore()
        settings = await settings_store.get_or_create_default()

        # Override config with database settings
        import json
        config.ALLOWED_FILE_EXTENSIONS = json.loads(settings["allowed_extensions"])
        config.UPLOAD_MAX_FILE_SIZE_MB = settings["max_file_size_mb"]
        print(f"[+] Upload settings loaded: extensions={config.ALLOWED_FILE_EXTENSIONS}, max_size={config.UPLOAD_MAX_FILE_SIZE_MB}MB")
        
    except Exception as e:
        print(f"[!] WARNING: Failed to initialize DuckDB: {e}")
        print("[!] Metadata storage will not be available")

    # Initialize Redis client for caching (before Ollama so we can pass it)
    print(f"[*] Connecting to Redis at {config.REDIS_HOST}:{config.REDIS_PORT}...")
    try:
        import redis.asyncio as redis

        state.redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            decode_responses=True,  # Return strings instead of bytes
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # Test connection
        await state.redis_client.ping()
        print("[+] Connected to Redis successfully")
    except Exception as e:
        print(f"[!] WARNING: Failed to connect to Redis: {e}")
        print("[!] Caching will be disabled")
        state.redis_client = None

    # Initialize clients (pass Redis to Ollama for embedding cache)
    state.ollama = OllamaClient(host=config.OLLAMA_HOST, redis_client=state.redis_client)
    state.qdrant = QdrantLocalClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)

    # Initialize activity tracker
    print("[*] Initializing activity tracker...")
    from src.utils.activity_tracker import ActivityTracker

    state.activity_tracker = ActivityTracker(redis_client=state.redis_client)
    print("[+] Activity tracker initialized")

    # Check Ollama connectivity and models
    print(f"[*] Checking Ollama connectivity at {config.OLLAMA_HOST}...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            response.raise_for_status()

            models_data = response.json()
            available_models = [m["name"] for m in models_data.get("models", [])]

            # Check required models
            required_models = [config.LLM_MODEL, config.EMBEDDING_MODEL]
            missing_models = [m for m in required_models if m not in available_models]

            if missing_models:
                print(f"[!] WARNING: Missing Ollama models: {missing_models}")
                print("[!] Please pull them with:")
                for model in missing_models:
                    print(f"    ollama pull {model}")
                print("[!] Continuing anyway, but some features may not work...")
            else:
                print(f"[+] Ollama connected. Available models: {available_models}")

    except Exception as e:
        print(f"[!] WARNING: Failed to connect to Ollama at {config.OLLAMA_HOST}")
        print(f"[!] Error: {e}")
        print("[!] Troubleshooting:")
        print("    1. Check if Ollama is running: ollama list")
        print("    2. If in Docker, ensure host.docker.internal is accessible")
        print("    3. Check firewall settings")
        print("[!] Continuing anyway, but LLM features will not work...")

    # Initialize Memory Service
    print("[*] Initializing Memory Service...")
    state.memory = MemoryService(
        ollama=state.ollama,
        qdrant=state.qdrant,
        embedding_model=config.EMBEDDING_MODEL
    )
    await state.memory.initialize()
    print("[+] Memory Service initialized")

    # Initialize LlamaIndex if enabled
    if config.USE_LLAMAINDEX:
        print("[*] Initializing LlamaIndex service...")
        try:
            from src.llm.llamaindex_service import LlamaIndexService

            state.llamaindex_service = LlamaIndexService(
                ollama_host=config.OLLAMA_HOST,
                llm_model=config.LLM_MODEL,
                embedding_model=config.EMBEDDING_MODEL,
                qdrant_host=config.QDRANT_HOST,
                qdrant_port=config.QDRANT_PORT,
                collection_name=config.QDRANT_COLLECTION,
                redis_client=state.redis_client,  # Pass Redis client for caching
            )

            # Check LlamaIndex health
            await state.llamaindex_service.check_ollama_connectivity()
            print("[+] LlamaIndex service initialized successfully")

        except Exception as e:
            print(f"[!] WARNING: Failed to initialize LlamaIndex: {e}")
            print("[!] Falling back to legacy RAG implementation...")
            state.llamaindex_service = None
    else:
        print("[i] LlamaIndex disabled (USE_LLAMAINDEX=false), using legacy RAG")

    # Connect to Neo4j
    print(f"[*] Connecting to Neo4j at {config.NEO4J_URI}...")
    try:
        state.graph = Neo4jGraphClient(
            uri=config.NEO4J_URI,
            username=config.NEO4J_USERNAME,
            password=config.NEO4J_PASSWORD,
            database=config.NEO4J_DATABASE,
        )
        print("[+] Connected to Neo4j")

        # Create indexes for performance
        state.graph.create_indexes()

    except Exception as e:
        print(f"[!] Failed to connect to Neo4j: {e}")
        print("[!] Please check your Neo4j credentials in .env file")
        raise

    # Initialize Parser and Extractor
    state.parser = CodeParser()
    state.extractor = GraphExtractor(neo4j_client=state.graph, code_parser=state.parser)
    print("[+] Initialized Code Parser and Graph Extractor")

    # Create agent
    state.agent = LocalSupervisorAgent(
        ollama=state.ollama,
        qdrant=state.qdrant,
        graph=state.graph,
        llm_model=config.LLM_MODEL,
        embedding_model=config.EMBEDDING_MODEL,
    )

    # Create Qdrant collection if needed
    try:
        await state.qdrant.create_collection("code_chunks", vector_size=768)
        print("[+] Created Qdrant collection")
    except Exception as e:
        print(f"[i] Collection may already exist: {e}")

    # Wire up ingestion tracker to WebSocket broadcast
    from .routers.admin import manager as ws_manager
    set_tracker_broadcast(ws_manager.broadcast)
    print("[+] Ingestion tracker connected to WebSocket")

    print("[+] All services initialized")
    print(f"[i] Graph stats: {state.graph.get_stats()}")

    yield

    # Cleanup
    print("[*] Shutting down gracefully...")

    # Close DuckDB connection
    print("[*] Closing DuckDB connection...")
    close_duckdb()

    # Close LlamaIndex service if initialized
    if state.llamaindex_service:
        print("[*] Closing LlamaIndex service...")
        # LlamaIndex cleanup handled by service

    # Close Redis connection
    if state.redis_client:
        print("[*] Closing Redis connection...")
        await state.redis_client.aclose()

    await state.ollama.close()
    await state.qdrant.close()
    if hasattr(state.graph, "close"):
        state.graph.close()

    print("[+] Shutdown complete")


# ==================== FastAPI App ====================

app = FastAPI(
    title="Financial Lineage Tool (Local with Neo4j)",
    description="Local development version using Ollama + Qdrant + Neo4j (cloud graph database)",
    version="1.0.0-local",
    lifespan=lifespan,
)

# Setup middleware
setup_cors(app)
setup_activity_tracking(app, state)
setup_error_handlers(app)

# Register routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(lineage.router)
app.include_router(ingest.router)
app.include_router(graph.router)
app.include_router(admin.router)
app.include_router(admin.admin_router)  # Admin endpoints without /api/v1 prefix
app.include_router(projects.router)  # Project management endpoints
app.include_router(database.router)  # Database schema endpoints
app.include_router(files.router)  # File upload endpoints
app.include_router(github.router)  # GitHub integration endpoints
app.include_router(metadata.router)  # Metadata query endpoints
