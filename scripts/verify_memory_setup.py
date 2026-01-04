
import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api.config import config
from src.services.memory_service import MemoryService
from src.services.ollama_service import OllamaClient
from src.services.qdrant_service import QdrantLocalClient

async def main():
    print("[*] Starting Memory Service Verification...")
    
    # Initialize Clients
    ollama = OllamaClient(host=config.OLLAMA_HOST)
    qdrant = QdrantLocalClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    
    memory = MemoryService(
        ollama=ollama,
        qdrant=qdrant,
        embedding_model=config.EMBEDDING_MODEL
    )
    
    session_id = str(uuid.uuid4())
    print(f"[*] Test Session ID: {session_id}")
    
    try:
        # 1. Initialize
        print("[*] 1. Initializing collection...")
        await memory.initialize()
        
        # 2. Store Interaction
        print("[*] 2. Storing interaction...")
        query = "What is the capital of France?"
        response = "The capital of France is Paris."
        await memory.store_interaction(session_id, query, response)
        
        # 3. Retrieve Context
        print("[*] 3. Retrieving context...")
        # Give Qdrant a moment to index? Usually instant for small data but good to be safe
        await asyncio.sleep(1)
        
        context = await memory.retrieve_context("France capital", session_id)
        print(f"[*] Retrieved Context:\n{context}")
        
        if "Paris" in context:
            print("[+] PASS: Context contains expected content.")
        else:
            print("[-] FAIL: Context missing expected content.")
            
        # 4. Delete Session
        print("[*] 4. Deleting session memory...")
        await memory.delete_session_memory(session_id)
        
        # 5. Verify Deletion
        print("[*] 5. Verifying deletion...")
        await asyncio.sleep(1)
        context_after = await memory.retrieve_context("France capital", session_id)
        if not context_after:
            print("[+] PASS: Memory deleted successfully.")
        else:
             # Note: logic might return OTHER session data if we implemented global search.
             # But our test data is unique enough? 
             # Actually retrieve_context currently searches GLOBAL history (per my implementation comment).
             # "For now, we'll retrieve globally (global knowledge)."
             # Wait, if retrieve_context doesn't filter by session_id (EXCLUDE), then it finds it.
             # Checks implementation: 
             # It does NOT filter by session currently.
             # But delete_session_memory deletes by session_id.
             # So if we delete it, it should be gone globally.
             
            if "Paris" not in context_after:
                print("[+] PASS: Memory deleted successfully (context empty or unrelated).")
            else:
                print(f"[-] FAIL: Memory still exists: {context_after}")

    except Exception as e:
        print(f"[!] ERROR: {e}")
    finally:
        await ollama.close()
        await qdrant.close()

if __name__ == "__main__":
    asyncio.run(main())
