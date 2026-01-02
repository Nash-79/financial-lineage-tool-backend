# Design: Backend Code Cleanup and Organization

## Overview

This change refactors the backend codebase to improve maintainability, readability, and developer productivity through systematic cleanup, modularization, and enhanced documentation.

## Architectural Decisions

### 1. API Modularization Strategy

**Decision:** Use FastAPI APIRouter pattern to split main_local.py into focused router modules.

**Rationale:**
- FastAPI's router pattern is designed for this purpose
- Enables parallel development on different endpoint groups
- Makes testing easier (test one router at a time)
- Improves code discoverability

**Implementation:**
```python
# src/api/main.py (formerly main_local.py)
from fastapi import FastAPI
from .routers import health, chat, lineage, ingest, graph, admin

app = FastAPI()
app.include_router(health.router, tags=["health"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(lineage.router, prefix="/api/lineage", tags=["lineage"])
# ...
```

**Trade-offs:**
- ✅ Smaller, focused files
- ✅ Better organization
- ⚠️ More imports to manage
- ⚠️ Slight increase in file count

### 2. Directory Structure Reorganization

**Decision:** Move from flat structure to layered architecture:
```
src/
  api/          # Presentation layer
  services/     # Business logic
  repositories/ # Data access (optional)
  utils/        # Shared utilities
```

**Rationale:**
- Clear separation of concerns
- Follows industry standard patterns
- Makes dependencies explicit
- Easier to unit test

**Migration Path:**
1. Create new directories
2. Move files with backward-compatible imports
3. Update imports gradually
4. Remove old locations

**Trade-offs:**
- ✅ Standard pattern, familiar to developers
- ✅ Clear dependency flow (API → Services → Repositories)
- ⚠️ Deeper nesting
- ⚠️ Import paths become longer

### 3. Deprecation vs Deletion

**Decision:** Delete unused code immediately (no deprecation period) for:
- `src/api/main.py` (Azure version)
- `src/knowledge_graph/cosmos_client.py`
- Duplicate file watchers
- Temporary documentation files

**Rationale:**
- Code is in version control (can recover if needed)
- No external consumers of these modules
- Reduces confusion for new developers
- Unused code has maintenance cost

**Safety Net:**
- Tag current state before deletion: `git tag pre-cleanup`
- Document removed code in change notes
- Keep removal as separate commit for easy revert

### 4. Logging Strategy

**Decision:** Use Python's `logging` module with structured logging format.

**Format:**
```python
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s',
    level=logging.INFO
)
```

**Rationale:**
- Standard Python approach
- Compatible with Docker log drivers
- Supports log aggregation tools
- No external dependencies

**Log Levels:**
- DEBUG: Detailed information for debugging
- INFO: General operational events
- WARNING: Unusual but handled situations
- ERROR: Errors that need attention

### 5. Documentation Standards

**Decision:** Use Google-style docstrings for consistency.

**Example:**
```python
def index_code_chunks(chunks: List[CodeChunk]) -> Dict[str, Any]:
    """Index code chunks into Qdrant using LlamaIndex.

    Args:
        chunks: List of CodeChunk objects from semantic_chunker.

    Returns:
        Dict with keys:
            - total_chunks: Number of chunks processed
            - total_documents: Number of documents indexed
            - status: "success" or "error"

    Raises:
        ConnectionError: If Qdrant is unavailable.
        ValueError: If chunks list is empty.

    Example:
        >>> chunks = chunker.chunk_file(sql_content)
        >>> result = index_code_chunks(chunks)
        >>> print(result["total_documents"])
        42
    """
```

**Rationale:**
- Widely adopted in Python community
- Supported by VS Code, PyCharm
- Generates good Sphinx docs
- More readable than Sphinx style

### 6. Error Handling Pattern

**Decision:** Create custom exception hierarchy in `src/utils/exceptions.py`.

**Hierarchy:**
```python
class LineageToolError(Exception):
    """Base exception for all lineage tool errors."""

class ConfigurationError(LineageToolError):
    """Raised when configuration is invalid."""

class IngestionError(LineageToolError):
    """Raised during document ingestion."""

class VectorStoreError(LineageToolError):
    """Raised for vector database errors."""
```

**Rationale:**
- Clear error categorization
- Easier to catch specific errors
- Better error messages
- Supports error recovery logic

### 7. Type Hints Strategy

**Decision:** Use Python 3.11 type hints with `from __future__ import annotations`.

**Examples:**
```python
from __future__ import annotations
from typing import Optional, List, Dict, Any

def process_query(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    ...
```

**Rationale:**
- Delayed evaluation improves import times
- Supports forward references
- Better IDE support
- Enables runtime type checking with Pydantic

## Implementation Phases

### Phase 1: Prepare (Low Risk)
1. Create new directory structure
2. Add missing utility modules
3. Set up logging configuration
4. Add type stubs

### Phase 2: Extract (Medium Risk)
1. Extract API routers from main_local.py
2. Extract middleware
3. Extract configuration
4. Update imports

### Phase 3: Reorganize (Medium Risk)
1. Move modules to new locations
2. Update import paths
3. Add backward-compatible imports
4. Update tests

### Phase 4: Cleanup (Low Risk)
1. Delete deprecated code
2. Remove temporary files
3. Consolidate scripts
4. Update .gitignore

### Phase 5: Document (Low Risk)
1. Add docstrings
2. Update README
3. Create architecture docs
4. Add inline comments

### Phase 6: Validate (Critical)
1. Run all tests
2. Check linting
3. Validate type hints
4. Test Docker deployment
5. Manual smoke testing

## Rollback Plan

If issues arise:

1. **Immediate**: Revert to `pre-cleanup` git tag
2. **Per-phase**: Each phase is a separate commit for granular rollback
3. **Import compatibility**: Deprecated imports redirect to new locations

## Validation Criteria

**Must Pass:**
- ✅ All existing tests pass
- ✅ Zero linting errors (ruff)
- ✅ Zero type errors (mypy --strict)
- ✅ Docker build succeeds
- ✅ Health check returns 200
- ✅ Can ingest sample SQL file
- ✅ Can execute RAG query

**Quality Gates:**
- 📊 Test coverage ≥ 80%
- 📏 Max file size: 500 lines
- 📝 All functions have docstrings
- 🔍 All modules have type hints

## Open Questions

1. **Q:** Should we maintain backward compatibility for old import paths?
   **A:** Yes, for one release cycle (add deprecation warnings).

2. **Q:** Should we split changes into multiple smaller changes?
   **A:** Consider splitting if total deltas > 50 files.

3. **Q:** How to handle breaking changes in API routes?
   **A:** No breaking changes - only internal refactoring.

4. **Q:** Should we auto-format all files with black?
   **A:** Yes, as part of Phase 1 (prepare).
