# Implementation Tasks

## 1. Admin & Endpoint Hardening
- [ ] 1.1 Secure `/admin/restart` with auth/role or restrict to local/dev builds; document behavior.
- [ ] 1.2 Validate/whitelist lineage `type` parameter to avoid Cypher injection and malformed queries.

## 2. Correctness Fixes
- [ ] 2.1 Fix legacy ingestion embed call to include the model parameter and handle errors clearly.
- [ ] 2.2 Use `node_types` stats for chat graph prompts so table/view/column counts are accurate.

## 3. Secrets & Config
- [ ] 3.1 Remove hardcoded Neo4j password default; require env var and fail closed with clear error.

## 4. Specs & Validation
- [ ] 4.1 Add spec deltas for `api-endpoints` and `llm-service` covering auth, validation, and embed call contract.
- [ ] 4.2 Add `deployment` delta forbidding default secrets and requiring fail-closed config for Neo4j creds.
- [ ] 4.3 Run `openspec validate harden-lineage-api --strict` and fix any issues.
