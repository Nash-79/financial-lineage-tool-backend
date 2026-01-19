# Change: Update Chat Models and Add Chat-Scoped Lineage

## Why
- Current free-tier model list is missing `qwen/qwen3-4b:free`, a verified $0/token model from OpenRouter.
- Chat model routing doesn't follow the optimal primary/secondary/tertiary ordering based on model capabilities (e.g., `/api/chat/text` should prioritize fast Gemini, not Llama).
- Chat responses include `graph_data` but it's not persisted per message, so users can't revisit answer-specific lineage after the conversation advances.
- No runtime verification mechanism to keep the free-tier model allowlist current as OpenRouter updates their free model collection.

## What Changes
- Add `qwen/qwen3-4b:free` to the `FREE_TIER_MODELS` whitelist.
- Update chat endpoint model routing to match recommended OpenRouter patterns:
  - `/api/chat/deep`: `deepseek-r1-0528:free` → `devstral-2512:free` → `gemini-2.0-flash-exp:free`
  - `/api/chat/graph`: `devstral-2512:free` → `deepseek-r1-0528:free` → `gemini-2.0-flash-exp:free`
  - `/api/chat/semantic`: `gemini-2.0-flash-exp:free` → `qwen3-4b:free` → `mistral-7b-instruct:free`
  - `/api/chat/text`: `gemini-2.0-flash-exp:free` → `mistral-7b-instruct:free` → `qwen3-4b:free`
- Add chat message artifact persistence: store `graph_data` per `(session_id, message_id)` in DuckDB.
- Add `GET /api/chat/session/{session_id}/message/{message_id}/graph` endpoint to retrieve persisted lineage graphs.
- Add optional background job to fetch OpenRouter's free models collection and update allowlist (with manual approval/verification step).

## Impact
- Affected specs: `api-endpoints`, `llm-service`, `data-organization`
- Affected code: `src/api/config.py`, `src/llm/free_tier.py`, `src/services/chat_service.py`, `src/storage/duckdb_client.py` (new chat_artifacts table), new router module
- Dependencies: No new dependencies; uses existing DuckDB and OpenRouter integration
