# Chat Overview

This document explains the chat endpoints and how they are currently wired.

## 1. Endpoints

All chat routes live under `/api/chat`:

- `POST /api/chat/deep` - deep analysis (top 10 context)
- `POST /api/chat/deep/stream` - SSE streaming variant
- `POST /api/chat/semantic` - semantic search over code chunks
- `POST /api/chat/graph` - graph-centric answers from Neo4j stats
- `POST /api/chat/text` - direct LLM response without RAG
- `POST /api/chat/title` - generate a short session title
- `DELETE /api/chat/session/{session_id}` - clear memory

Details and request/response payloads are in `../api/API_REFERENCE.md`.

## 2. Routing logic

All `/api/chat/*` endpoints use direct retrieval (Qdrant + Neo4j) and generate
responses via OpenRouter free-tier models. LlamaIndex is not used for chat
generation. `/api/chat/deep/stream` runs the same retrieval + generation flow
and streams the final answer back over SSE.

## 3. Data sources

- **Vector search**: Qdrant `code_chunks` collection
- **Graph lookups**: Neo4j nodes and upstream/downstream traversal
- **Memory**: optional Qdrant-backed chat memory when `session_id` is provided

## 4. System prompts

Legacy deep chat uses a lineage-focused system prompt defined in
`src/services/agent_service.py` ("You are a Financial Data Lineage Agent...").

## 5. Models

LLM and embedding models are controlled by `.env` and `src/api/config.py`:

- `EMBEDDING_MODEL` for local embeddings (Ollama)
- `CHAT_*_PRIMARY_MODEL`, `CHAT_*_SECONDARY_MODEL`, `CHAT_*_TERTIARY_MODEL`
  for OpenRouter chat generation
- `CHAT_*_TEMPERATURE` and `CHAT_TIMEOUT_*_SECONDS` for per-endpoint tuning

The `/api/v1/config` endpoint exposes the active chat model mappings and the
free-tier whitelist.
