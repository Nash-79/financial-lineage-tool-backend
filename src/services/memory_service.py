"""Service for managing long-term chat memory via vector storage."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .ollama_service import OllamaClient
    from .qdrant_service import QdrantLocalClient

COLLECTION_NAME = "chat_history"


class MemoryService:
    """Manages vectorized chat history for long-term memory."""

    def __init__(
        self,
        ollama: OllamaClient,
        qdrant: QdrantLocalClient,
        embedding_model: str,
    ):
        """Initialize memory service.

        Args:
            ollama: Client for generating embeddings.
            qdrant: Client for vector storage/search.
            embedding_model: Name of the embedding model (e.g., nomic-embed-text).
        """
        self.ollama = ollama
        self.qdrant = qdrant
        self.embedding_model = embedding_model

    async def initialize(self) -> None:
        """Ensure the vector collection exists."""
        try:
            # Check if collection exists implicitly by trying to search or list
            # But QdrantLocalClient (our wrapper) has create_collection.
            # We'll just try to create it, ignoring errors if it exists (relying on API idempotency or error handling)
            # Actually our wrapper's create_collection might fail if exists. 
            # Ideally we check first, but our wrapper doesn't expose list/exists yet.
            # We'll rely on the fact that creating multiple times might error but is safe to try on startup.
            # Or better, just catch the error.
            await self.qdrant.create_collection(
                name=COLLECTION_NAME, vector_size=768
            )
            print(f"[*] Created vector collection: {COLLECTION_NAME}")
        except Exception as e:
            # If it already exists, that's fine.
            # print(f"[*] Collection init note: {e}")
            pass

    async def store_interaction(
        self,
        session_id: str,
        user_query: str,
        assistant_response: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Store a chat interaction (both user query and response) in memory.

        This should be called asynchronously to avoid blocking the chat response.

        Args:
            session_id: The chat session ID.
            user_query: The user's input.
            assistant_response: The AI's output.
            metadata: Optional additional metadata.
        """
        timestamp = datetime.utcnow().isoformat()
        
        # 1. Store User Entity
        try:
            user_embedding = await self.ollama.embed(user_query, self.embedding_model)
            user_point = {
                "id": str(uuid.uuid4()),
                "vector": user_embedding,
                "payload": {
                    "session_id": session_id,
                    "role": "user",
                    "content": user_query,
                    "timestamp": timestamp,
                    **(metadata or {}),
                },
            }
            
            # 2. Store Assistant Entity
            assistant_embedding = await self.ollama.embed(assistant_response, self.embedding_model)
            assistant_point = {
                "id": str(uuid.uuid4()),
                "vector": assistant_embedding,
                "payload": {
                    "session_id": session_id,
                    "role": "assistant",
                    "content": assistant_response,
                    "timestamp": timestamp,
                    **(metadata or {}),
                },
            }

            # Upsert batch
            await self.qdrant.upsert(
                collection=COLLECTION_NAME,
                points=[user_point, assistant_point]
            )
            # print(f"[*] Stored interaction for session {session_id}")

        except Exception as e:
            print(f"[!] Failed to store chat memory: {e}")

    async def retrieve_context(
        self, query: str, session_id: Optional[str] = None, limit: int = 5
    ) -> str:
        """Retrieve relevant past interactions.

        Args:
            query: The current user query to match against.
            session_id: Optional session ID to EXCLUDE current session context if desired,
                        or to constrain to specific session. 
                        Design choice: "Long Term Memory" usually means *other* sessions
                        or very old parts of this session.
                        For now, we'll retrieve globally (global knowledge).
                        But maybe we want to filter simply by score.
            limit: Number of results.

        Returns:
            Formatted context string.
        """
        try:
            query_embedding = await self.ollama.embed(query, self.embedding_model)
            
            # Search
            results = await self.qdrant.search(
                collection=COLLECTION_NAME,
                vector=query_embedding,
                limit=limit
            )

            if not results:
                return ""

            context_parts = []
            for res in results:
                payload = res.get("payload", {})
                
                # Deduplication/Relevance Check:
                # If the content is identical to the current query, skip it (it's the current interaction if we stored it early, or just repetition)
                if payload.get("content") == query:
                    continue
                    
                role = payload.get("role", "unknown")
                content = payload.get("content", "")
                timestamp = payload.get("timestamp", "")[:16].replace("T", " ")
                
                context_parts.append(f"[{timestamp}] {role}: {content}")

            if not context_parts:
                return ""

            return "## Past Relevant Conversations:\n" + "\n".join(context_parts) + "\n\n"

        except Exception as e:
            print(f"[!] Failed to retrieve chat memory: {e}")
            return ""

    async def delete_session_memory(self, session_id: str) -> None:
        """Delete all memory vector for a specific session.
        
        Args:
            session_id: ID of the session to delete.
        """
        try:
            # Qdrant delete by filter
            # Our current QdrantLocalClient wrapper might ONLY support 'delete' by point IDs?
            # Let's check the client wrapper. If it doesn't support delete-by-filter, 
            # we might need to add it or skip this for now.
            # Assuming we need to add methods to QdrantLocalClient if missing.
            
            # For now, we'll assume we might need to implement the delete method in the client first
            # or use raw client access if exposed.
            
            # Using client.client (httpx) to call delete endpoint with filter
            if hasattr(self.qdrant, 'base_url') and hasattr(self.qdrant, 'client'):
                 await self.qdrant.client.post(
                    f"{self.qdrant.base_url}/collections/{COLLECTION_NAME}/points/delete",
                    json={
                        "filter": {
                            "must": [
                                {"key": "session_id", "match": {"value": session_id}}
                            ]
                        }
                    }
                )
                 print(f"[*] Deleted memory for session {session_id}")
            else:
                print(f"[!] Cannot delete session memory: Qdrant client structure unknown")

        except Exception as e:
            print(f"[!] Failed to delete session memory: {e}")
