# Change: Harden Lineage API and Admin Surfaces

## Why
- Admin restart endpoint is unauthenticated, enabling arbitrary process restarts/DoS.
- Lineage `type` filter is directly interpolated into Cypher, allowing injection or query failures.
- Chat graph prompt shows zero counts because it uses wrong stats fields.
- Legacy ingestion embed call omits the model parameter, causing runtime failure when LlamaIndex is disabled.
- Neo4j password is hardcoded in config defaults, leaking secrets and masking missing env configuration.

## What Changes
- Add requirements to secure `/admin/restart` with auth or restrict to local/dev only.
- Validate lineage `type` labels/whitelist to prevent Cypher injection.
- Fix chat graph stats to use node type counts in prompts.
- Require embed calls to supply/validate the model parameter across ingestion/chat paths.
- Prohibit checked-in default secrets and fail closed when required credentials are absent.

## Impact
- Affected specs: `api-endpoints`, `llm-service`, `deployment`
- Affected code (future): admin router, lineage router, chat graph stats, ingestion embed call, config defaults
