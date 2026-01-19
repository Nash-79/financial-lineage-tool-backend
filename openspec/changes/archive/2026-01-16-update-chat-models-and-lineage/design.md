## Context
The system currently uses hardcoded free-tier model lists and chat endpoint routing that doesn't fully leverage model capabilities. The `graph_data` field exists in chat responses but is ephemeral - once the conversation advances, users can't retrieve the lineage graph that was generated for a specific answer.

## Goals / Non-Goals
- Goals:
  - Add Qwen 3-4B to verified $0/token models for fast semantic/text endpoints
  - Optimize model routing to match model strengths (DeepSeek R1 for reasoning, Devstral for code/graph, Gemini for speed)
  - Persist chat-scoped lineage graphs so users can revisit answer-specific subgraphs
  - Add retrieval endpoint for message-specific graph data
  - Establish pattern for runtime OpenRouter model verification (future: auto-update allowlist)
- Non-Goals:
  - Automatic allowlist updates without manual review (defer to future iteration)
  - Changing the global lineage page (this is chat-specific lineage only)
  - Modifying LLM fallback/retry logic (already implemented)

## Decisions
- Decision: Add `qwen/qwen3-4b:free` to `FREE_TIER_MODELS` based on OpenRouter verification ($0/M input, $0/M output)
- Decision: Reorder chat endpoint routing:
  - `/deep`: reasoning-first (DeepSeek R1) with code fallback (Devstral)
  - `/graph`: code/structure-first (Devstral) with reasoning fallback (DeepSeek R1)
  - `/semantic` and `/text`: speed-first (Gemini, Qwen, Mistral 7B)
- Decision: Store `graph_data` in DuckDB `chat_artifacts` table keyed by `(session_id, message_id, artifact_type="graph")`
- Decision: Add `GET /api/chat/session/{session_id}/message/{message_id}/graph` to retrieve persisted graphs
- Decision: Document (but defer implementation of) periodic OpenRouter free models sync job

## Risks / Trade-offs
- Storage cost: Chat artifacts table will grow with every message that includes graph data (mitigated by DuckDB snapshot cleanup)
- Qwen model might have rate limits or availability issues (fallback chain handles this)
- Model routing changes could temporarily affect response quality if OpenRouter free tier changes availability

## Migration Plan
- Add `chat_artifacts` table to DuckDB schema with `(session_id, message_id, artifact_type, artifact_data, created_at)` columns
- No backfill needed (new feature)
- Gracefully handle missing graph data for old messages (return 404)

## Resolved Questions
- **Q: Should we persist graph data for all endpoints or only `/deep` and `/graph`?**
  - **A: Persist for all endpoints that return `graph_data` in their response.** The storage cost is minimal (JSON blob per message), and having consistent behavior simplifies the API contract. The chat service already determines when to include `graph_data` based on query type detection, so persistence follows the same logic—if `graph_data` is non-empty in the response, persist it.
- **Q: Should frontend auto-fetch graph data when viewing chat history?**
  - **A: Defer to frontend OpenSpec proposal.** Backend provides the retrieval endpoint; frontend decides when to call it.

## Open Questions
- None remaining for this iteration
