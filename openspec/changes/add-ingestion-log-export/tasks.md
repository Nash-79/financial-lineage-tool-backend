## 1. Implementation
- [x] 1.1 Extend ingestion tracker to persist JSONL log events per session and track log path.
- [x] 1.2 Add verbose flag handling in upload and GitHub ingestion flows; record extra debug events when enabled.
- [x] 1.3 Add ingestion log retrieval endpoint (JSON/JSONL + download) and wire it into the API router.
- [x] 1.4 Add tests for ingestion log persistence and retrieval.
- [x] 1.5 Update API docs if endpoints change.

## 2. Validation
- [ ] 2.1 python -m pytest tests/unit/api -q
