# Operations Specification Change: Visual Graph Rendering

## Metadata
* **Author**: Antigravity
* **Status**: Proposed
* **Created**: 2026-01-04
* **Target Completion**: 2026-01-04

## Motivation
Users need a visual representation of data lineage relationships directly in the chat interface, rather than just text descriptions or raw JSON.

## Proposed Changes

### Backend
1. **Schema Update**: Add `graph_data` (nodes, edges) to `ChatResponse`.
2. **Endpoint Update**: 
    - `chat_graph`: Return full graph structure.
    - `chat_deep`: Return relevant subgraph for entities found.

### Frontend
1. **Component**: implementation of `GraphVisualizer` using `@xyflow/react`.
2. **Integration**: Render graph within `MessageItem` when `graph_data` is present.
3. **Features**:
    - Auto-layout (using `dagre` or similar if needed, or simple force layout).
    - Interactive nodes (click to see details).
    - "Expand" view (modal).

## Verification
- Manual verification of graph rendering for "Show me lineage of X".
